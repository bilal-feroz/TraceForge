from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "services" / "demo-target"
DEFAULT_TARGET = ROOT / "fixtures" / "generated-demo-repositories" / "traceforge-demo"

LOCK_BLOCK = """    # TRACEFORGE_VISITS_START
    with tracer.start_as_current_span(
        "db.sqlite.insert",
        attributes={"db.system": "sqlite", "db.operation.name": "INSERT"},
    ):
        connection = sqlite3.connect(DB_PATH, timeout=0.01)
        try:
            connection.execute("PRAGMA busy_timeout=10")
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "INSERT INTO visits(visitor, created_at) VALUES (?, ?)",
                (payload.visitor, time.time()),
            )
            # Regression: unrelated work holds the write lock under concurrent traffic.
            time.sleep(0.08)
            connection.commit()
            visit_id = int(cursor.lastrowid or 0)
        except sqlite3.OperationalError as exc:
            connection.rollback()
            logger.exception(
                "database is locked",
                extra={"error.type": type(exc).__name__, "db.system": "sqlite"},
            )
            raise
        finally:
            connection.close()
    # TRACEFORGE_VISITS_END"""

LATENCY_DECLARATION = """event_values: list[int] = []
event_total = 0
event_lock = Lock()"""

LATENCY_BLOCK = """    # TRACEFORGE_EVENTS_START
    with event_lock:
        event_values.append(payload.value)
        # Regression: each request rescans all retained state and delay grows with it.
        total = sum(event_values)
        retained = len(event_values)
        time.sleep(min(retained * 0.00008, 0.08))
    # TRACEFORGE_EVENTS_END"""


def run(*args: str, cwd: Path) -> None:
    completed = subprocess.run(  # noqa: S603 - arguments are internal Git commands
        list(args),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())


def remove_readonly(function: object, path: str, _: object) -> None:
    os.chmod(path, stat.S_IWRITE)
    if callable(function):
        function(path)


def replace_marked(text: str, start: str, end: str, replacement: str) -> str:
    start_index = text.index(start)
    end_index = text.index(end, start_index) + len(end)
    return text[:start_index] + replacement + text[end_index:]


def write_app(target: Path, content: str) -> None:
    (target / "app.py").write_text(content, encoding="utf-8", newline="\n")


def commit(target: Path, message: str, tag: str) -> None:
    run("git", "add", ".", cwd=target)
    run("git", "commit", "-m", message, cwd=target)
    run("git", "tag", "-f", tag, cwd=target)


def bootstrap(target: Path, *, force: bool = False) -> Path:
    target = target.resolve()
    allowed_root = (ROOT / "fixtures" / "generated-demo-repositories").resolve()
    try:
        target.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(f"target must be under {allowed_root}") from exc
    if target.exists():
        if not force:
            raise FileExistsError(f"{target} already exists; pass --force to rebuild it")
        shutil.rmtree(target, onexc=remove_readonly)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        SOURCE,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "*.db"),
    )
    run("git", "init", "-b", "main", cwd=target)
    run("git", "config", "user.name", "TraceForge Demo", cwd=target)
    run("git", "config", "user.email", "demo@traceforge.local", cwd=target)
    baseline = (target / "app.py").read_text(encoding="utf-8")
    commit(target, "baseline: bounded event state and short SQLite transactions", "demo-baseline")

    run("git", "checkout", "-b", "regression/lock", cwd=target)
    lock_source = replace_marked(
        baseline,
        "    # TRACEFORGE_VISITS_START",
        "    # TRACEFORGE_VISITS_END",
        LOCK_BLOCK,
    )
    write_app(target, lock_source)
    commit(target, "regression: hold SQLite write lock during simulated work", "demo-lock")

    run("git", "checkout", "main", cwd=target)
    run("git", "checkout", "-b", "regression/latency", cwd=target)
    latency_source = baseline.replace(
        "event_values: deque[int] = deque(maxlen=1_000)\nevent_total = 0\nevent_lock = Lock()",
        LATENCY_DECLARATION,
    )
    latency_source = replace_marked(
        latency_source,
        "    # TRACEFORGE_EVENTS_START",
        "    # TRACEFORGE_EVENTS_END",
        LATENCY_BLOCK,
    )
    write_app(target, latency_source)
    commit(target, "regression: rescan unbounded event history per request", "demo-latency")

    run("git", "checkout", "main", cwd=target)
    run("git", "checkout", "-b", "control/no-regression", cwd=target)
    control_source = baseline.replace(
        'return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}',
        'return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION, '
        '"role": "demo-target"}',
    )
    write_app(target, control_source)
    commit(target, "control: add descriptive health metadata", "demo-control")

    run("git", "checkout", "regression/lock", cwd=target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the TraceForge demo Git repository")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = bootstrap(args.target, force=args.force)
    print(result)


if __name__ == "__main__":
    main()
