from __future__ import annotations

import shutil
import socket
import sys
from dataclasses import asdict, dataclass
from typing import Any

from traceforge.process import ProcessError, run_process
from traceforge.settings import Settings
from traceforge.signoz import SigNozMCPClient, SigNozUnavailable


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    status: str
    detail: str
    required: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _command_check(name: str, args: list[str], *, required: bool = True) -> DoctorCheck:
    executable = shutil.which(args[0])
    if executable is None:
        return DoctorCheck(name, "missing", f"{args[0]} is not on PATH", required)
    try:
        result = run_process(args, timeout_seconds=15, check=False)
    except ProcessError as exc:
        return DoctorCheck(name, "error", str(exc), required)
    output = (result.stdout or result.stderr).strip().splitlines()
    detail = output[0] if output else executable
    return DoctorCheck(name, "ok" if result.returncode == 0 else "error", detail, required)


def _port_check(port: int) -> DoctorCheck:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            return DoctorCheck("target port", "busy", f"127.0.0.1:{port}: {exc}", True)
    return DoctorCheck("target port", "ok", f"127.0.0.1:{port} is available", True)


async def run_doctor(settings: Settings, *, target_port: int = 8099) -> list[DoctorCheck]:
    checks = [
        DoctorCheck(
            "Python",
            "ok" if sys.version_info >= (3, 12) else "unsupported",
            sys.version.split()[0] + " (TraceForge requires 3.12+)",
            True,
        ),
        _command_check("uv", ["uv", "--version"]),
        _command_check("Node", ["node", "--version"], required=False),
        _command_check(
            "pnpm", ["pnpm.cmd" if sys.platform == "win32" else "pnpm", "--version"], required=False
        ),
        _command_check("Git", ["git", "--version"]),
        _command_check("k6", ["k6", "version"]),
        _command_check("Docker", ["docker", "--version"], required=False),
        _port_check(target_port),
    ]
    ingestion = settings.telemetry_ingestion_configured
    checks.append(
        DoctorCheck(
            "OTLP ingestion",
            "ok" if ingestion else "unconfigured",
            (
                "OTLP endpoint and ingestion authentication are configured"
                if ingestion
                else "set OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_HEADERS"
            ),
            True,
        )
    )
    if settings.signoz_mcp_configured:
        client = SigNozMCPClient(settings)
        try:
            tools = await client.connect_and_discover()
            client.validate_capabilities()
        except SigNozUnavailable as exc:
            checks.append(DoctorCheck("SigNoz MCP", "error", str(exc), True))
        else:
            checks.append(
                DoctorCheck(
                    "SigNoz MCP",
                    "ok",
                    f"connected; discovered {len(tools)} tools",
                    True,
                )
            )
    else:
        checks.append(
            DoctorCheck(
                "SigNoz MCP",
                "unconfigured",
                "set SIGNOZ_MCP_URL, SIGNOZ_INSTANCE_URL, and SIGNOZ_API_KEY",
                True,
            )
        )
    return checks
