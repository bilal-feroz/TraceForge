from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from traceforge.ledger import canonical_json
from traceforge.models import (
    ExperimentWindow,
    LogEvidence,
    MCPInvocation,
    Phase,
    TelemetryEvidence,
    TraceEvidence,
    utc_now,
)
from traceforge.security import redact
from traceforge.settings import Settings
from traceforge.signoz_metrics import metric_evidence
from traceforge.telemetry import workflow_span

EVIDENCE_ROW_LIMIT = 200

REQUIRED_CAPABILITIES = {
    "signoz_list_services",
    "signoz_list_metrics",
    "signoz_get_field_keys",
    "signoz_get_field_values",
    "signoz_get_service_top_operations",
    "signoz_aggregate_traces",
    "signoz_search_traces",
    "signoz_get_trace_details",
    "signoz_aggregate_logs",
    "signoz_search_logs",
    "signoz_query_metrics",
}

DASHBOARD_CAPABILITIES = {
    "signoz_list_dashboards",
    "signoz_create_dashboard",
    "signoz_update_dashboard",
}


class SigNozUnavailable(RuntimeError):
    pass


class SigNozCapabilityError(SigNozUnavailable):
    pass


def _connection_error(exc: BaseException) -> str:
    """Classify a transport failure without echoing credentials or private URLs."""
    nested = getattr(exc, "exceptions", ())
    detail = " ".join(_connection_error_text(item) for item in nested) or str(exc)
    lowered = detail.lower()
    if "400" in lowered and "x-signoz-url" in lowered:
        return (
            "SigNoz MCP configuration rejected X-SigNoz-URL; use the full "
            "https:// instance origin with no dashboard path"
        )
    if "401" in lowered or "unauthorized" in lowered:
        return "SigNoz MCP authentication failed; verify the active service-account API key"
    if "403" in lowered or "forbidden" in lowered:
        return "SigNoz MCP permission denied; verify the service account has telemetry read access"
    if "timeout" in lowered or "timed out" in lowered:
        return "SigNoz MCP connection timed out"
    if any(marker in lowered for marker in ("connect", "dns", "ssl", "tls")):
        return "SigNoz MCP network or TLS connection failed"
    return "SigNoz MCP connection failed during initialization or tool discovery"


def _first_signoz_error(exc: BaseException) -> SigNozUnavailable | None:
    """Find a SigNoz failure inside the ExceptionGroup anyio raises when a task group unwinds."""
    if isinstance(exc, SigNozUnavailable):
        return exc
    for nested in getattr(exc, "exceptions", ()):
        found = _first_signoz_error(nested)
        if found is not None:
            return found
    return None


def _dashboard_write_error(exc: SigNozUnavailable) -> SigNozUnavailable:
    """Name the read-only service account explicitly instead of reporting a transport failure."""
    detail = str(exc)
    if "403" in detail or "editors/admins" in detail.lower():
        return SigNozCapabilityError(
            "the SigNoz service account is read-only, so dashboard writes are refused with HTTP "
            "403; publish with an editor or admin API key, or import the JSON by hand"
        )
    return exc


def _tool_error_text(result: Any) -> str:
    text = " ".join(
        str(getattr(block, "text", "")).strip() for block in getattr(result, "content", [])
    ).strip()
    return text[:300] if text else "no detail returned"


def _connection_error_text(exc: BaseException) -> str:
    nested = getattr(exc, "exceptions", ())
    if nested:
        return " ".join(_connection_error_text(item) for item in nested)
    return str(exc)


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _result_payload(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured
    blocks = getattr(result, "content", [])
    values: list[Any] = []
    for block in blocks:
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            values.append(json.loads(text))
        except (json.JSONDecodeError, TypeError):
            values.append(text)
    if len(values) == 1:
        return values[0]
    return values


def _summarize(value: Any) -> str:
    if isinstance(value, dict):
        return f"object with keys: {', '.join(sorted(map(str, value))[:15])}"
    if isinstance(value, list):
        return f"list with {len(value)} items"
    return str(value)[:240]


def _nested_rows(value: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("rows", "spans", "logs", "items", "results", "data"):
        nested = value.get(key)
        if isinstance(nested, dict | list):
            found = _rows(nested)
            if found:
                return found
    return []


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        found: list[dict[str, Any]] = []
        items = [item for item in value if isinstance(item, dict)]
        for item in items:
            found.extend(_nested_rows(item))
        return found or items
    if isinstance(value, dict):
        return _nested_rows(value)
    return []


def _row_data(row: dict[str, Any]) -> dict[str, Any]:
    nested = row.get("data")
    if not isinstance(nested, dict):
        return row
    payload = dict(nested)
    if "timestamp" not in payload and row.get("timestamp") is not None:
        payload["timestamp"] = row["timestamp"]
    return payload


def _contains_correlation(value: Any, run_id: str) -> bool:
    if isinstance(value, dict):
        return any(
            (key == "traceforge.run.id" and item == run_id) or _contains_correlation(item, run_id)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_correlation(item, run_id) for item in value)
    return False


def _escape_filter(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _dashboard_id(listing: Any, title: str) -> str | None:
    """Find an existing dashboard UUID by exact title so republishing is idempotent."""
    for row in _rows(listing):
        candidate = row.get("title") or row.get("name")
        if isinstance(candidate, str) and candidate.strip() == title:
            for key in ("id", "uuid", "dashboard_id"):
                value = row.get(key)
                if isinstance(value, str) and value:
                    return value
    return None


class SigNozMCPClient:
    def __init__(
        self,
        settings: Settings,
        *,
        invocation_sink: Callable[[MCPInvocation], None] | None = None,
    ) -> None:
        self.settings = settings
        self.invocation_sink = invocation_sink
        self.tools: dict[str, dict[str, Any]] = {}
        self.invocations: list[MCPInvocation] = []
        self.correlation_run_id: str | None = None

    def _configured(self) -> tuple[str, dict[str, str]]:
        if not self.settings.signoz_mcp_configured:
            raise SigNozUnavailable(
                "SigNoz verification unavailable: set SIGNOZ_MCP_URL, "
                "SIGNOZ_INSTANCE_URL, and SIGNOZ_API_KEY"
            )
        assert self.settings.signoz_mcp_url
        assert self.settings.signoz_instance_url
        assert self.settings.signoz_api_key
        headers = {
            "SIGNOZ-API-KEY": self.settings.signoz_api_key,
            "X-SigNoz-URL": self.settings.signoz_instance_url,
        }
        return self.settings.signoz_mcp_url, headers

    async def _session(self) -> tuple[Any, Any, Any, Any]:
        raise RuntimeError("sessions are managed by connect()")

    async def _recorded_call(
        self,
        session: ClientSession,
        name: str,
        arguments: dict[str, Any],
        *,
        attempts: int = 3,
    ) -> Any:
        if name not in self.tools:
            raise SigNozCapabilityError(f"SigNoz MCP tool not discovered: {name}")
        schema = self.tools[name]
        allowed = set(schema.get("properties", {}))
        unknown = set(arguments) - allowed
        if unknown:
            raise SigNozCapabilityError(
                f"arguments not present in discovered schema for {name}: {sorted(unknown)}"
            )
        started_at = utc_now()
        start_clock = time.perf_counter()
        invocation_id = str(uuid4())
        error: str | None = None
        response: Any = None
        with workflow_span(
            "signoz.mcp.call",
            **{
                "traceforge.mcp.tool": name,
                "traceforge.run.id": self.correlation_run_id or "",
            },
        ) as span:
            for attempt in range(attempts):
                try:
                    result = await session.call_tool(name, arguments)
                    if getattr(result, "isError", False) or getattr(result, "is_error", False):
                        raise SigNozUnavailable(
                            f"{name} returned an MCP tool error: {_tool_error_text(result)}"
                        )
                    response = _result_payload(result)
                    error = None
                    break
                except (httpx.TimeoutException, httpx.TransportError, SigNozUnavailable) as exc:
                    error = str(exc)
                    if attempt + 1 >= attempts:
                        break
                    await asyncio.sleep(0.5 * (2**attempt))
            span.set_attribute("traceforge.mcp.attempts", attempt + 1)
            if error is not None:
                span.set_attribute("traceforge.success", False)
        duration_ms = (time.perf_counter() - start_clock) * 1_000
        safe_request = redact(arguments)
        invocation = MCPInvocation(
            invocation_id=invocation_id,
            tool_name=name,
            started_at=started_at,
            duration_ms=duration_ms,
            request_digest=_digest(safe_request),
            sanitized_request=safe_request,
            response_digest=_digest(redact(response)) if response is not None else None,
            response_summary=_summarize(redact(response)) if response is not None else None,
            success=error is None,
            error=error,
        )
        self.invocations.append(invocation)
        if self.invocation_sink:
            self.invocation_sink(invocation)
        if error is not None:
            raise SigNozUnavailable(f"{name} failed after {attempts} attempts: {error}")
        return response

    async def connect_and_discover(self) -> list[str]:
        url, headers = self._configured()
        timeout = httpx.Timeout(self.settings.mcp_timeout_seconds)
        try:
            async with httpx.AsyncClient(
                headers=headers, timeout=timeout, follow_redirects=True
            ) as http_client:
                async with streamable_http_client(url, http_client=http_client) as streams:
                    read, write, _ = streams
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        response = await session.list_tools()
                        self.tools = {
                            tool.name: (
                                getattr(tool, "inputSchema", None)
                                or getattr(tool, "input_schema", None)
                                or {}
                            )
                            for tool in response.tools
                        }
        except SigNozUnavailable:
            raise
        except Exception as exc:
            raise SigNozUnavailable(_connection_error(exc)) from None
        return sorted(self.tools)

    def validate_capabilities(self) -> None:
        missing = sorted(REQUIRED_CAPABILITIES - self.tools.keys())
        if missing:
            raise SigNozCapabilityError(
                "SigNoz MCP is missing required investigation tools: " + ", ".join(missing)
            )

    async def publish_dashboard(self, definition: dict[str, Any]) -> dict[str, Any]:
        """Create the dashboard, or replace it in place when the title already exists."""
        url, headers = self._configured()
        title = str(definition.get("title", "")).strip()
        if not title:
            raise SigNozUnavailable("the dashboard definition is missing a title")
        timeout = httpx.Timeout(max(self.settings.mcp_timeout_seconds, 60))
        try:
            async with httpx.AsyncClient(
                headers=headers, timeout=timeout, follow_redirects=True
            ) as http_client:
                async with streamable_http_client(url, http_client=http_client) as streams:
                    read, write, _ = streams
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        response = await session.list_tools()
                        self.tools = {
                            tool.name: (
                                getattr(tool, "inputSchema", None)
                                or getattr(tool, "input_schema", None)
                                or {}
                            )
                            for tool in response.tools
                        }
                        missing = sorted(DASHBOARD_CAPABILITIES - self.tools.keys())
                        if missing:
                            raise SigNozCapabilityError(
                                "the SigNoz service account cannot write dashboards; missing "
                                + ", ".join(missing)
                            )
                        existing = await self._recorded_call(
                            session,
                            "signoz_list_dashboards",
                            {"limit": 1000, "searchContext": f"publish dashboard {title}"},
                            attempts=1,
                        )
                        target = _dashboard_id(existing, title)
                        if target is None:
                            payload = await self._recorded_call(
                                session,
                                "signoz_create_dashboard",
                                {**definition, "searchContext": f"publish dashboard {title}"},
                                attempts=1,
                            )
                            action = "created"
                        else:
                            payload = await self._recorded_call(
                                session,
                                "signoz_update_dashboard",
                                {
                                    "id": target,
                                    "dashboard": definition,
                                    "searchContext": f"republish dashboard {title}",
                                },
                                attempts=1,
                            )
                            action = "updated"
        except SigNozUnavailable as exc:
            raise _dashboard_write_error(exc) from None
        except Exception as exc:
            nested = _first_signoz_error(exc)
            if nested is not None:
                raise _dashboard_write_error(nested) from None
            raise SigNozUnavailable(_connection_error(exc)) from None
        return {"action": action, "title": title, "response": payload}

    async def investigate(
        self,
        *,
        run_id: str,
        service_name: str,
        endpoint: str,
        window: ExperimentWindow,
    ) -> TelemetryEvidence:
        url, headers = self._configured()
        self.correlation_run_id = run_id
        timeout = httpx.Timeout(self.settings.mcp_timeout_seconds)
        start_ms = int((window.started_at - timedelta(seconds=5)).timestamp() * 1_000)
        end_ms = int((window.ended_at + timedelta(seconds=10)).timestamp() * 1_000)
        trace_filter = f"attribute.traceforge.run.id = '{_escape_filter(run_id)}'"
        log_filter = f"attribute.traceforge.run.id = '{_escape_filter(run_id)}'"

        async with httpx.AsyncClient(
            headers=headers, timeout=timeout, follow_redirects=True
        ) as http_client:
            async with streamable_http_client(url, http_client=http_client) as streams:
                read, write, _ = streams
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    response = await session.list_tools()
                    self.tools = {
                        tool.name: (
                            getattr(tool, "inputSchema", None)
                            or getattr(tool, "input_schema", None)
                            or {}
                        )
                        for tool in response.tools
                    }
                    self.validate_capabilities()

                    await self._recorded_call(
                        session,
                        "signoz_get_field_keys",
                        self._schema_args(
                            "signoz_get_field_keys",
                            {"signal": "traces", "searchText": "traceforge"},
                        ),
                    )
                    await self._recorded_call(
                        session,
                        "signoz_get_field_keys",
                        self._schema_args(
                            "signoz_get_field_keys",
                            {"signal": "logs", "searchText": "traceforge"},
                        ),
                    )
                    await self._recorded_call(
                        session,
                        "signoz_get_field_values",
                        self._schema_args(
                            "signoz_get_field_values",
                            {
                                "signal": "traces",
                                "name": "traceforge.run.id",
                                "searchText": run_id,
                                "fieldContext": "attribute",
                            },
                        ),
                    )
                    await self._recorded_call(
                        session,
                        "signoz_list_metrics",
                        self._schema_args(
                            "signoz_list_metrics",
                            {
                                "searchText": "traceforge.demo.request.duration",
                                "start": start_ms,
                                "end": end_ms,
                                "limit": 20,
                            },
                        ),
                    )
                    service_response = await self._recorded_call(
                        session,
                        "signoz_list_services",
                        self._schema_args(
                            "signoz_list_services",
                            {"start": start_ms, "end": end_ms},
                        ),
                    )
                    if service_name.lower() not in canonical_json(service_response).lower():
                        raise SigNozUnavailable(
                            f"expected service {service_name!r} is absent in the experiment window"
                        )
                    await self._recorded_call(
                        session,
                        "signoz_get_service_top_operations",
                        self._schema_args(
                            "signoz_get_service_top_operations",
                            {
                                "service": service_name,
                                "start": start_ms,
                                "end": end_ms,
                            },
                        ),
                    )
                    traces_response: Any = None
                    deadline = time.monotonic() + self.settings.ingestion_timeout_seconds
                    while time.monotonic() < deadline:
                        traces_response = await self._recorded_call(
                            session,
                            "signoz_search_traces",
                            self._schema_args(
                                "signoz_search_traces",
                                {
                                    "filter": trace_filter,
                                    "service": service_name,
                                    "start": start_ms,
                                    "end": end_ms,
                                    "limit": EVIDENCE_ROW_LIMIT,
                                },
                            ),
                        )
                        if _rows(traces_response):
                            break
                        await asyncio.sleep(3)
                    trace_rows = _rows(traces_response)
                    if not trace_rows:
                        raise SigNozUnavailable(
                            "telemetry did not arrive before the bounded ingestion timeout"
                        )
                    trace_id = str(trace_rows[0].get("trace_id", trace_rows[0].get("traceId", "")))
                    if trace_id:
                        await self._recorded_call(
                            session,
                            "signoz_get_trace_details",
                            self._schema_args(
                                "signoz_get_trace_details",
                                {
                                    "traceId": trace_id,
                                    "start": start_ms,
                                    "end": end_ms,
                                    "includeSpans": True,
                                },
                            ),
                        )
                    metrics_response = await self._recorded_call(
                        session,
                        "signoz_query_metrics",
                        self._schema_args(
                            "signoz_query_metrics",
                            {
                                "metricName": "traceforge.demo.request.duration",
                                "filter": trace_filter,
                                "start": start_ms,
                                "end": end_ms,
                                "requestType": "time_series",
                            },
                        ),
                    )
                    logs_response = await self._recorded_call(
                        session,
                        "signoz_search_logs",
                        self._schema_args(
                            "signoz_search_logs",
                            {
                                "filter": log_filter,
                                "service": service_name,
                                "start": start_ms,
                                "end": end_ms,
                                "limit": EVIDENCE_ROW_LIMIT,
                            },
                        ),
                    )
                    await self._recorded_call(
                        session,
                        "signoz_aggregate_traces",
                        self._schema_args(
                            "signoz_aggregate_traces",
                            {
                                "aggregation": "p95",
                                "aggregateOn": "durationNano",
                                "groupBy": "name",
                                "filter": trace_filter,
                                "service": service_name,
                                "start": start_ms,
                                "end": end_ms,
                                "limit": 20,
                            },
                        ),
                    )
                    await self._recorded_call(
                        session,
                        "signoz_aggregate_logs",
                        self._schema_args(
                            "signoz_aggregate_logs",
                            {
                                "aggregation": "count",
                                "groupBy": "severity_text",
                                "filter": log_filter,
                                "service": service_name,
                                "start": start_ms,
                                "end": end_ms,
                                "limit": 20,
                            },
                        ),
                    )

        log_rows = _rows(logs_response)
        if not any(_contains_correlation(row, run_id) for row in log_rows):
            raise SigNozUnavailable(
                "returned telemetry is missing the exact traceforge.run.id correlation attribute"
            )
        traces = [self._trace_evidence(row) for row in trace_rows]
        if not any(item.trace_id for item in traces):
            raise SigNozUnavailable("returned trace rows do not contain trace IDs")
        logs = [self._log_evidence(row) for row in log_rows]
        return TelemetryEvidence(
            run_id=run_id,
            service_name=service_name,
            window=window,
            endpoint=endpoint,
            available=True,
            traces=traces,
            logs=logs,
            metrics=metric_evidence(
                metrics_response, default_name="traceforge.demo.request.duration"
            ),
            mcp_invocations=list(self.invocations),
            tools_discovered=sorted(self.tools),
        )

    def _schema_args(self, tool_name: str, candidate: dict[str, Any]) -> dict[str, Any]:
        schema = self.tools.get(tool_name, {})
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise SigNozCapabilityError(f"invalid discovered schema for {tool_name}")
        required = schema.get("required", [])
        arguments = {key: value for key, value in candidate.items() if key in properties}
        missing = [key for key in required if key not in arguments]
        if missing:
            raise SigNozCapabilityError(
                f"cannot satisfy discovered required arguments for {tool_name}: {missing}"
            )
        return arguments

    @staticmethod
    def _trace_evidence(row: dict[str, Any]) -> TraceEvidence:
        row = _row_data(row)
        duration_nano = row.get("duration_nano", row.get("durationNano", 0))
        try:
            duration_ms = float(duration_nano) / 1_000_000
        except (TypeError, ValueError):
            duration_ms = 0
        return TraceEvidence(
            trace_id=str(row.get("trace_id", row.get("traceId", ""))),
            span_id=str(row.get("span_id", row.get("spanId", ""))) or None,
            operation=str(row.get("name", row.get("operation", "unknown"))),
            duration_ms=max(0, duration_ms),
            status=str(row.get("status_code_string", row.get("has_error", "unknown"))),
            attributes=redact(row),
        )

    @staticmethod
    def _log_evidence(row: dict[str, Any]) -> LogEvidence:
        row = _row_data(row)
        raw_timestamp = row.get("timestamp", row.get("time", utc_now().isoformat()))
        try:
            if isinstance(raw_timestamp, int | float):
                if raw_timestamp > 100_000_000_000_000_000:
                    raw_timestamp /= 1_000_000_000
                elif raw_timestamp > 100_000_000_000:
                    raw_timestamp /= 1_000
                timestamp = datetime.fromtimestamp(raw_timestamp).astimezone()
            else:
                timestamp = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
        except (ValueError, OSError):
            timestamp = utc_now()
        raw_body = row.get("body", row.get("message", ""))
        body = canonical_json(raw_body) if isinstance(raw_body, dict | list) else str(raw_body)
        return LogEvidence(
            timestamp=timestamp,
            body=body[:4_000],
            severity=str(row.get("severity_text", row.get("severity", "UNSPECIFIED"))),
            trace_id=str(row.get("trace_id", row.get("traceId", ""))) or None,
            attributes=redact(row),
        )


def unavailable_evidence(
    *,
    run_id: str,
    service_name: str,
    endpoint: str,
    window: ExperimentWindow,
    reason: str,
    phase: Phase,
) -> TelemetryEvidence:
    if window.phase != phase:
        window = window.model_copy(update={"phase": phase})
    message = (
        reason
        if reason.startswith("SigNoz verification unavailable")
        else f"SigNoz verification unavailable: {reason}"
    )
    return TelemetryEvidence(
        run_id=run_id,
        service_name=service_name,
        window=window,
        endpoint=endpoint,
        available=False,
        unavailable_reason=message,
    )
