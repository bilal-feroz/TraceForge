from __future__ import annotations

import asyncio
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from traceforge.doctor import run_doctor
from traceforge.engine import RunEngine, RunNotFound
from traceforge.models import Profile, RepositoryTarget
from traceforge.patching import PatchError
from traceforge.process import run_process
from traceforge.report import render_report
from traceforge.settings import get_settings
from traceforge.signoz import SigNozMCPClient, SigNozUnavailable
from traceforge.telemetry import configure_telemetry

app = typer.Typer(
    name="traceforge",
    help="Load-test a change, investigate it in SigNoz, and prove a governed fix.",
    no_args_is_help=True,
)
runs_app = typer.Typer(help="Inspect and resume durable runs.")
ledger_app = typer.Typer(help="Verify the tamper-evident run ledger.")
patch_app = typer.Typer(help="Inspect governed patch proposals.")
demo_app = typer.Typer(help="Run a reproducible TraceForge scenario.")
dashboard_app = typer.Typer(help="Publish the native SigNoz release-proof dashboard.")
app.add_typer(runs_app, name="runs")
app.add_typer(ledger_app, name="ledger")
app.add_typer(patch_app, name="patch")
app.add_typer(demo_app, name="demo")
app.add_typer(dashboard_app, name="dashboard")

DASHBOARD_TEMPLATE = (
    Path(__file__).resolve().parents[4]
    / "infra"
    / "signoz"
    / "traceforge-release-proof.dashboard.json"
)


@app.callback()
def main() -> None:
    """Force UTF-8 console output so redirected Windows pipes keep report characters."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def output(value: Any, *, json_mode: bool) -> None:
    if json_mode:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        elif hasattr(value, "__dict__"):
            value = value.__dict__
        typer.echo(json.dumps(value, indent=2, default=str))
    else:
        typer.echo(value)


def engine() -> RunEngine:
    settings = get_settings()
    configure_telemetry(
        settings.service_name,
        endpoint=settings.otlp_endpoint,
        header_value=settings.otlp_headers,
        ingestion_key=settings.signoz_ingestion_key,
    )
    return RunEngine(settings)


@app.command()
def doctor(
    json_mode: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
    target_port: Annotated[int, typer.Option(help="Local demo target port.")] = 8099,
) -> None:
    """Check the complete local and SigNoz environment."""
    checks = asyncio.run(run_doctor(get_settings(), target_port=target_port))
    if json_mode:
        output([item.as_dict() for item in checks], json_mode=True)
    else:
        for item in checks:
            typer.echo(f"{item.status.upper():12} {item.name:18} {item.detail}")
    if any(item.required and item.status != "ok" for item in checks):
        raise typer.Exit(1)


@app.command()
def analyze(
    repo: Annotated[Path, typer.Option("--repo", exists=True, file_okay=False)],
    base_ref: Annotated[str, typer.Option("--base-ref")],
    candidate_ref: Annotated[str, typer.Option("--candidate-ref")],
    target_url: Annotated[str, typer.Option("--target-url")],
    profile: Annotated[Profile, typer.Option()] = Profile.DEMO,
    target_command: Annotated[
        str | None,
        typer.Option(
            "--target-command",
            help="Trusted-local command; requires TRACEFORGE_TRUSTED_LOCAL_MODE=true.",
        ),
    ] = None,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Analyze base and candidate revisions with a real k6/SigNoz experiment."""
    command = shlex.split(target_command, posix=os.name != "nt") if target_command else None
    run_engine = engine()
    run = run_engine.create(
        RepositoryTarget(
            path=repo,
            base_ref=base_ref,
            candidate_ref=candidate_ref,
            target_url=target_url,
            profile=profile,
            target_command=command,
        )
    )
    if not json_mode:
        typer.echo(f"Intake  {run.run_id}")
    run = asyncio.run(run_engine.analyze(run.run_id))
    output(run, json_mode=json_mode)
    if run.terminal_state and run.terminal_state.value in {"FAILED", "BLOCKED"}:
        raise typer.Exit(2)


@runs_app.command("list")
def list_runs(
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    items = engine().store.list()
    if json_mode:
        output([item.model_dump(mode="json") for item in items], json_mode=True)
        return
    if not items:
        typer.echo("No TraceForge runs have been recorded.")
        return
    for item in items:
        terminal = item.terminal_state.value if item.terminal_state else "active"
        typer.echo(f"{item.run_id}  {item.stage.value:24} {terminal}")


@runs_app.command("show")
def show_run(
    run_id: str,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    try:
        run = engine().get(run_id)
    except RunNotFound:
        typer.echo("Run not found.", err=True)
        raise typer.Exit(1) from None
    output(run if json_mode else render_report(run), json_mode=json_mode)


@runs_app.command("resume")
def resume_run(
    run_id: str,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    run_engine = engine()
    try:
        run = asyncio.run(run_engine.analyze(run_id))
    except RunNotFound:
        typer.echo("Run not found.", err=True)
        raise typer.Exit(1) from None
    output(run, json_mode=json_mode)


@ledger_app.command("verify")
def ledger_verify(
    run_id: str,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    try:
        result = engine().ledger_verify(run_id)
    except RunNotFound:
        typer.echo("Run not found.", err=True)
        raise typer.Exit(1) from None
    payload = {
        "valid": result.valid,
        "event_count": result.event_count,
        "terminal_state": result.terminal_state,
        "errors": result.errors,
    }
    output(payload if json_mode else json.dumps(payload, indent=2), json_mode=json_mode)
    if not result.valid:
        raise typer.Exit(3)


@patch_app.command("show")
def patch_show(run_id: str) -> None:
    try:
        typer.echo(engine().patch_text(run_id))
    except (RunNotFound, PatchError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None


@patch_app.command("apply")
def patch_apply(run_id: str) -> None:
    """Apply only in a temporary worktree and start proof verification."""
    run_engine = engine()
    try:
        run = asyncio.run(run_engine.analyze(run_id))
    except (RunNotFound, PatchError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    typer.echo(render_report(run))


@app.command()
def verify(run_id: str) -> None:
    """Resume the governed sandbox proof loop for a run."""
    patch_apply(run_id)


def demo(scenario: str, *, profile: Profile, port: int, json_mode: bool) -> None:
    repository_root = Path(__file__).resolve().parents[4]
    repo = repository_root / "fixtures" / "generated-demo-repositories" / "traceforge-demo"
    if not (repo / ".git").exists():
        run_process(
            [sys.executable, str(repository_root / "scripts" / "bootstrap_demo_repo.py")],
            cwd=repository_root,
            timeout_seconds=120,
        )
    refs = {
        "lock": "demo-lock",
        "latency": "demo-latency",
        "control": "demo-control",
    }
    settings = get_settings().model_copy(
        update={
            "trusted_local_mode": True,
            "allowed_repo_roots": [repo.parent.resolve()],
        }
    )
    configure_telemetry(
        settings.service_name,
        endpoint=settings.otlp_endpoint,
        header_value=settings.otlp_headers,
        ingestion_key=settings.signoz_ingestion_key,
    )
    run_engine = RunEngine(settings)
    run = run_engine.create(
        RepositoryTarget(
            path=repo,
            base_ref="demo-baseline",
            candidate_ref=refs[scenario],
            target_url=f"http://127.0.0.1:{port}",
            profile=profile,
            target_command=[
                sys.executable,
                "-m",
                "uvicorn",
                "app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
        )
    )
    if not json_mode:
        typer.echo(f"Intake     {run.run_id}")
        typer.echo(f"Scope      demo-{scenario}")
        typer.echo("Stress     baseline → candidate")
        typer.echo("Observe    SigNoz is required for a supported verdict")
    completed = asyncio.run(run_engine.analyze(run.run_id))
    output(completed if json_mode else render_report(completed), json_mode=json_mode)
    if completed.terminal_state and completed.terminal_state.value == "FAILED":
        raise typer.Exit(2)


@dashboard_app.command("publish")
def dashboard_publish(
    template: Annotated[
        Path,
        typer.Option("--template", exists=True, dir_okay=False, help="Dashboard definition JSON."),
    ] = DASHBOARD_TEMPLATE,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Validate the definition without calling SigNoz.")
    ] = False,
) -> None:
    """Create or replace the "TraceForge — Release Proof" dashboard through SigNoz MCP."""
    definition = json.loads(template.read_text(encoding="utf-8"))
    widgets = definition.get("widgets", [])
    layout = {item["i"] for item in definition.get("layout", [])}
    identifiers = {item["id"] for item in widgets}
    if layout != identifiers:
        typer.echo(
            f"layout and widget identifiers disagree: {sorted(layout ^ identifiers)}",
            err=True,
        )
        raise typer.Exit(1)
    typer.echo(
        f"{definition['title']}: {len(widgets)} widgets, {len(definition['variables'])} variables"
    )
    if dry_run:
        typer.echo("dry run: the definition is internally consistent and was not published")
        return
    settings = get_settings()
    configure_telemetry(
        settings.service_name,
        endpoint=settings.otlp_endpoint,
        header_value=settings.otlp_headers,
        ingestion_key=settings.signoz_ingestion_key,
    )
    client = SigNozMCPClient(settings)
    try:
        result = asyncio.run(client.publish_dashboard(definition))
    except SigNozUnavailable as exc:
        typer.echo(str(exc), err=True)
        typer.echo(
            "Import infra/signoz/traceforge-release-proof.dashboard.json manually from "
            "Dashboards > New dashboard > Import JSON.",
            err=True,
        )
        raise typer.Exit(1) from None
    typer.echo(f"{result['action']}: {result['title']}")


@demo_app.command("lock")
def demo_lock(
    profile: Annotated[Profile, typer.Option()] = Profile.DEMO,
    port: Annotated[int, typer.Option()] = 8099,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    demo("lock", profile=profile, port=port, json_mode=json_mode)


@demo_app.command("latency")
def demo_latency(
    profile: Annotated[Profile, typer.Option()] = Profile.DEMO,
    port: Annotated[int, typer.Option()] = 8099,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    demo("latency", profile=profile, port=port, json_mode=json_mode)


@demo_app.command("control")
def demo_control(
    profile: Annotated[Profile, typer.Option()] = Profile.QUICK,
    port: Annotated[int, typer.Option()] = 8099,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    demo("control", profile=profile, port=port, json_mode=json_mode)
