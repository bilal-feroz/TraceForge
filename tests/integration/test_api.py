import httpx
import pytest

from traceforge.api import app


@pytest.mark.integration
async def test_health_contract() -> None:
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://traceforge.test"
        ) as client:
            response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["service"] == "traceforge-orchestrator"
