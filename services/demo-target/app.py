from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, Request, Response
from opentelemetry import metrics, trace
from pydantic import BaseModel, Field

from telemetry_setup import configure_telemetry, instrument_app

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "traceforge-demo-target")
SERVICE_VERSION = os.getenv("TRACEFORGE_GIT_SHA", "development")
DB_PATH = Path(os.getenv("DEMO_DB_PATH", "traceforge-demo.db"))

configure_telemetry(SERVICE_NAME, SERVICE_VERSION)
logger = logging.getLogger("traceforge.demo-target")
tracer = trace.get_tracer("traceforge.demo-target")
meter = metrics.get_meter("traceforge.demo-target")
request_counter = meter.create_counter(
    "traceforge.demo.requests",
    unit="{request}",
    description="Requests handled by the TraceForge demo target",
)
request_latency = meter.create_histogram(
    "traceforge.demo.request.duration",
    unit="ms",
    description="Demo target handler duration",
)
event_values: deque[int] = deque(maxlen=1_000)
event_total = 0
event_lock = Lock()


def init_db() -> None:
    with sqlite3.connect(DB_PATH, timeout=5) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        connection.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="TraceForge Demo Target",
    version="1.0.0",
    lifespan=lifespan,
)
instrument_app(app)


class VisitIn(BaseModel):
    visitor: str = Field(default="traceforge", min_length=1, max_length=80)


class EventIn(BaseModel):
    value: int = Field(default=1, ge=-1_000, le=1_000)


def correlation(request: Request) -> dict[str, str]:
    mapping = {
        "traceforge.run.id": request.headers.get("X-TraceForge-Run-Id", ""),
        "traceforge.phase": request.headers.get("X-TraceForge-Phase", ""),
        "traceforge.scenario": request.headers.get("X-TraceForge-Scenario", ""),
        "git.commit.sha": request.headers.get("X-TraceForge-Git-Sha", SERVICE_VERSION),
    }
    return {key: value[:200] for key, value in mapping.items() if value}


@app.middleware("http")
async def correlate_request(request: Request, call_next: Any) -> Response:
    attributes = correlation(request)
    active = trace.get_current_span()
    for key, value in attributes.items():
        active.set_attribute(key, value)
    active.set_attribute("deployment.environment", "preproduction")
    active.set_attribute("service.version", SERVICE_VERSION)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        active.set_attribute("error.type", type(exc).__name__)
        active.set_attribute("error.message", str(exc)[:500])
        logger.exception(
            "request failed",
            extra={**attributes, "error.type": type(exc).__name__},
        )
        raise
    duration_ms = (time.perf_counter() - started) * 1_000
    request_counter.add(1, {**attributes, "http.route": request.url.path})
    request_latency.record(duration_ms, {**attributes, "http.route": request.url.path})
    logger.info(
        json.dumps(
            {
                "event": "request.complete",
                "route": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 3),
                **attributes,
            },
            separators=(",", ":"),
        ),
        extra=attributes,
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.post("/api/visits", status_code=201)
def create_visit(payload: VisitIn) -> dict[str, Any]:
    started = time.perf_counter()
    # TRACEFORGE_VISITS_START
    with tracer.start_as_current_span(
        "db.sqlite.insert",
        attributes={"db.system": "sqlite", "db.operation.name": "INSERT"},
    ):
        with sqlite3.connect(DB_PATH, timeout=5) as connection:
            connection.execute("PRAGMA busy_timeout=5000")
            cursor = connection.execute(
                "INSERT INTO visits(visitor, created_at) VALUES (?, ?)",
                (payload.visitor, time.time()),
            )
            connection.commit()
            visit_id = int(cursor.lastrowid or 0)
    time.sleep(0.02)
    # TRACEFORGE_VISITS_END
    return {
        "id": visit_id,
        "visitor": payload.visitor,
        "duration_ms": round((time.perf_counter() - started) * 1_000, 3),
    }


@app.post("/api/events", status_code=201)
def create_event(payload: EventIn) -> dict[str, Any]:
    # TRACEFORGE_EVENTS_START
    global event_total
    with event_lock:
        if len(event_values) == event_values.maxlen:
            event_total -= event_values[0]
        event_values.append(payload.value)
        event_total += payload.value
        total = event_total
        retained = len(event_values)
    # TRACEFORGE_EVENTS_END
    return {"accepted": True, "retained": retained, "aggregate": total}
