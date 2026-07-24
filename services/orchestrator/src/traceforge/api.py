from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse

from traceforge.engine import RunEngine, RunNotFound
from traceforge.events import event_bus
from traceforge.models import RepositoryTarget, RunCreateRequest
from traceforge.report import render_report
from traceforge.settings import get_settings
from traceforge.signoz import SigNozMCPClient, SigNozUnavailable
from traceforge.telemetry import (
    configure_structured_logging,
    configure_telemetry,
    instrument_fastapi,
)

settings = get_settings()
engine = RunEngine(settings)
tasks: dict[str, asyncio.Task[Any]] = {}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_structured_logging()
    configure_telemetry(
        settings.service_name,
        endpoint=settings.otlp_endpoint,
        header_value=settings.otlp_headers,
        ingestion_key=settings.signoz_ingestion_key,
    )
    yield
    for task in list(tasks.values()):
        if not task.done():
            task.cancel()
    if tasks:
        await asyncio.gather(*tasks.values(), return_exceptions=True)


app = FastAPI(
    title="TraceForge Orchestrator API",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
router = APIRouter(prefix="/api/v1")


def get_run(run_id: str) -> Any:
    try:
        return engine.get(run_id)
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


def launch(run_id: str) -> None:
    existing = tasks.get(run_id)
    if existing and not existing.done():
        raise HTTPException(status_code=409, detail="run is already executing")
    task = asyncio.create_task(engine.analyze(run_id), name=f"traceforge:{run_id}")
    tasks[run_id] = task


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(request: RunCreateRequest) -> Any:
    target = RepositoryTarget(
        path=Path(request.repository),
        base_ref=request.base_ref,
        candidate_ref=request.candidate_ref,
        target_url=request.target_url,
        profile=request.profile,
        target_command=None,
    )
    run = engine.create(target)
    launch(run.run_id)
    return run


@router.get("/runs")
async def list_runs() -> Any:
    return engine.store.list()


@router.get("/runs/{run_id}")
async def show_run(run_id: str) -> Any:
    return get_run(run_id)


@router.post("/runs/{run_id}/resume", status_code=status.HTTP_202_ACCEPTED)
async def resume_run(run_id: str) -> Any:
    run = get_run(run_id)
    if run.terminal_state:
        raise HTTPException(status_code=409, detail="terminal runs cannot be resumed")
    launch(run_id)
    return run


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str) -> Any:
    get_run(run_id)
    task = tasks.get(run_id)
    if task and not task.done():
        task.cancel()
    return engine.cancel(run_id)


async def sse_stream(run_id: str, request: Request) -> AsyncIterator[str]:
    for event in event_bus.history(run_id):
        yield f"event: {event.get('type', 'message')}\ndata: {json.dumps(event)}\n\n"
    queue = event_bus.subscribe(run_id)
    try:
        while not await request.is_disconnected():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield f"event: {event.get('type', 'message')}\ndata: {json.dumps(event)}\n\n"
    finally:
        event_bus.unsubscribe(run_id, queue)


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, request: Request) -> Any:
    get_run(run_id)
    return StreamingResponse(
        sse_stream(run_id, request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}/evidence")
async def run_evidence(run_id: str) -> Any:
    run = get_run(run_id)
    return {"experiments": run.experiments, "telemetry": run.telemetry}


@router.get("/runs/{run_id}/diagnosis")
async def run_diagnosis(run_id: str) -> Any:
    run = get_run(run_id)
    if run.diagnosis is None:
        raise HTTPException(status_code=404, detail="diagnosis not available")
    return run.diagnosis


@router.get("/runs/{run_id}/patch")
async def run_patch(run_id: str) -> Any:
    run = get_run(run_id)
    if run.patch is None:
        raise HTTPException(status_code=404, detail="patch not available")
    return {"proposal": run.patch, "audit": run.patch_audit}


@router.post("/runs/{run_id}/verify", status_code=status.HTTP_202_ACCEPTED)
async def verify_run(run_id: str) -> Any:
    run = get_run(run_id)
    if run.patch is None:
        raise HTTPException(status_code=409, detail="run has no patch to verify")
    launch(run_id)
    return run


@router.get("/runs/{run_id}/report", response_class=PlainTextResponse)
async def run_report(run_id: str) -> str:
    return render_report(get_run(run_id))


@router.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "traceforge-orchestrator",
        "version": "0.1.0",
        "signoz_configured": settings.signoz_mcp_configured,
    }


@router.get("/integrations/signoz/status")
async def signoz_status() -> dict[str, Any]:
    client = SigNozMCPClient(settings)
    try:
        tools = await client.connect_and_discover()
        client.validate_capabilities()
    except SigNozUnavailable as exc:
        return {
            "available": False,
            "message": "SigNoz verification unavailable",
            "detail": str(exc),
        }
    return {"available": True, "tool_count": len(tools), "tools": tools}


app.include_router(router)
instrument_fastapi(app)
