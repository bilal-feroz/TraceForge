from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from traceforge.models import Stage, TerminalState, TraceForgeRun

MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        stage TEXT NOT NULL,
        terminal_state TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS transitions (
        event_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES runs(run_id),
        previous_state TEXT NOT NULL,
        next_state TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        outcome TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_transitions_run_id ON transitions(run_id);
    CREATE TABLE IF NOT EXISTS mcp_invocations (
        invocation_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES runs(run_id),
        tool_name TEXT NOT NULL,
        started_at TEXT NOT NULL,
        duration_ms REAL NOT NULL,
        success INTEGER NOT NULL,
        payload_json TEXT NOT NULL
    );
    """,
]


class RunStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {
                int(row[0]) for row in connection.execute("SELECT version FROM schema_migrations")
            }
            for version, migration in enumerate(MIGRATIONS, start=1):
                if version in applied:
                    continue
                connection.executescript(migration)
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, datetime.now().astimezone().isoformat()),
                )

    def save(self, run: TraceForgeRun) -> None:
        payload = run.model_dump_json()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO runs(run_id, stage, terminal_state, created_at, updated_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    stage = excluded.stage,
                    terminal_state = excluded.terminal_state,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                (
                    run.run_id,
                    run.stage.value,
                    run.terminal_state.value if run.terminal_state else None,
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                    payload,
                ),
            )

    def get(self, run_id: str) -> TraceForgeRun | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return TraceForgeRun.model_validate_json(row["payload_json"]) if row else None

    def list(self, *, limit: int = 100) -> list[TraceForgeRun]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [TraceForgeRun.model_validate_json(row["payload_json"]) for row in rows]

    def transition_exists(self, event_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM transitions WHERE event_id = ?", (event_id,)
            ).fetchone()
        return row is not None

    def record_transition(
        self,
        *,
        event_id: str,
        run_id: str,
        previous_state: Stage | TerminalState,
        next_state: Stage | TerminalState,
        occurred_at: datetime,
        outcome: str,
    ) -> bool:
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO transitions(
                        event_id, run_id, previous_state, next_state, occurred_at, outcome
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        run_id,
                        previous_state.value,
                        next_state.value,
                        occurred_at.isoformat(),
                        outcome,
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def transition_event_ids(self, run_id: str) -> dict[str, str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT event_id, next_state FROM transitions WHERE run_id = ? ORDER BY occurred_at",
                (run_id,),
            ).fetchall()
        return {row["event_id"]: row["next_state"] for row in rows}

    def save_mcp_invocation(self, run_id: str, invocation: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO mcp_invocations(
                    invocation_id, run_id, tool_name, started_at, duration_ms, success, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invocation["invocation_id"],
                    run_id,
                    invocation["tool_name"],
                    str(invocation["started_at"]),
                    float(invocation["duration_ms"]),
                    int(bool(invocation["success"])),
                    json.dumps(invocation, default=str),
                ),
            )
