from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from mcp.server.fastmcp import FastMCP

from traceforge.models import ExperimentWindow, Phase
from traceforge.settings import Settings
from traceforge.signoz import REQUIRED_CAPABILITIES, SigNozMCPClient


def controlled_server() -> FastMCP[Any]:
    server: FastMCP[Any] = FastMCP(
        "controlled-signoz",
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )

    def register(name: str, function: Any) -> None:
        server.add_tool(function, name=name)

    def list_services(start: int, end: int) -> dict[str, Any]:
        return {"data": [{"serviceName": "traceforge-demo-target"}]}

    def list_metrics(searchText: str, start: int, end: int, limit: int = 20) -> dict[str, Any]:
        return {"data": [{"name": "traceforge.demo.request.duration"}]}

    def field_keys(signal: str, searchText: str = "") -> dict[str, Any]:
        return {"data": [{"name": "traceforge.run.id", "signal": signal}]}

    def field_values(
        signal: str,
        name: str,
        searchText: str = "",
        fieldContext: str = "",
    ) -> dict[str, Any]:
        return {"data": [{"value": searchText, "name": name, "signal": signal}]}

    def top_operations(service: str, start: int, end: int) -> dict[str, Any]:
        return {"data": [{"name": "POST /api/visits", "p95": 80}]}

    def search_traces(
        filter: str,
        service: str,
        start: int,
        end: int,
        limit: int = 200,
    ) -> dict[str, Any]:
        return {
            "data": [
                {
                    "traceId": "a" * 32,
                    "spanId": "b" * 16,
                    "name": "POST /api/visits",
                    "durationNano": 80_000_000,
                    "status": "OK",
                }
            ]
        }

    def trace_details(
        traceId: str,
        start: int,
        end: int,
        includeSpans: bool = True,
    ) -> dict[str, Any]:
        return {"traceId": traceId, "spans": [{"name": "db.sqlite.insert"}]}

    def search_logs(
        filter: str,
        service: str,
        start: int,
        end: int,
        limit: int = 200,
    ) -> dict[str, Any]:
        return {
            "data": [
                {
                    "timestamp": start,
                    "body": "request.complete",
                    "severity_text": "INFO",
                    "traceId": "a" * 32,
                }
            ]
        }

    def aggregate_traces(
        aggregation: str,
        aggregateOn: str,
        groupBy: str,
        filter: str,
        service: str,
        start: int,
        end: int,
        limit: int,
    ) -> dict[str, Any]:
        return {"data": [{"name": "POST /api/visits", "value": 80}]}

    def aggregate_logs(
        aggregation: str,
        groupBy: str,
        filter: str,
        service: str,
        start: int,
        end: int,
        limit: int,
    ) -> dict[str, Any]:
        return {"data": [{"severity_text": "INFO", "value": 1}]}

    def query_metrics(
        metricName: str,
        filter: str,
        start: int,
        end: int,
        requestType: str,
    ) -> dict[str, Any]:
        return {
            "data": {
                "result": [
                    {
                        "metric": {"__name__": metricName, "traceforge.phase": "candidate"},
                        "values": [[start / 1_000, "81.5"], [end / 1_000, "84.0"]],
                    }
                ]
            }
        }

    tools = {
        "signoz_list_services": list_services,
        "signoz_list_metrics": list_metrics,
        "signoz_get_field_keys": field_keys,
        "signoz_get_field_values": field_values,
        "signoz_get_service_top_operations": top_operations,
        "signoz_search_traces": search_traces,
        "signoz_get_trace_details": trace_details,
        "signoz_search_logs": search_logs,
        "signoz_aggregate_traces": aggregate_traces,
        "signoz_aggregate_logs": aggregate_logs,
        "signoz_query_metrics": query_metrics,
    }
    for name, function in tools.items():
        register(name, function)
    return server


@pytest.mark.integration
async def test_sig_noz_client_discovers_and_queries_controlled_server(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    server = controlled_server()
    app = server.streamable_http_app()
    original_client = httpx.AsyncClient

    def local_client(**kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.ASGITransport(app=app)
        return original_client(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", local_client)
    settings = Settings(
        TRACEFORGE_DATA_DIR=tmp_path,
        SIGNOZ_MCP_URL="http://127.0.0.1:8000/mcp",
        SIGNOZ_INSTANCE_URL="http://signoz.test",
        SIGNOZ_API_KEY="test-only-key",
        TRACEFORGE_MCP_TIMEOUT_SECONDS=2,
    )
    client = SigNozMCPClient(settings)
    now = datetime.now(UTC)

    async with app.router.lifespan_context(app):
        discovered = await client.connect_and_discover()
        client.validate_capabilities()
        evidence = await client.investigate(
            run_id="controlled-run",
            service_name="traceforge-demo-target",
            endpoint="/api/visits",
            window=ExperimentWindow(
                phase=Phase.CANDIDATE,
                started_at=now - timedelta(seconds=10),
                ended_at=now,
            ),
        )

    assert REQUIRED_CAPABILITIES.issubset(discovered)
    assert evidence.available
    assert evidence.traces[0].trace_id == "a" * 32
    assert evidence.logs[0].body == "request.complete"
    assert evidence.metrics[0].points[-1][1] == 84.0
    assert all(invocation.success for invocation in evidence.mcp_invocations)
