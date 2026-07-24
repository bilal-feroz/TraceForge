from pathlib import Path

import pytest

from traceforge.k6 import render_script
from traceforge.load_plan import create_plan
from traceforge.models import AffectedEndpoint, LoadTestPlan, Profile


def endpoint() -> AffectedEndpoint:
    return AffectedEndpoint(
        path="/api/items",
        method="POST",
        source_file="app.py",
        line=10,
        confidence=0.9,
        reason="changed route",
        request_body_example={"name": "item"},
    )


def test_plan_has_correlation_headers_and_bounded_demo_duration() -> None:
    plan = create_plan(endpoint(), profile=Profile.DEMO, target_url="http://127.0.0.1:8099")
    assert plan.maximum_duration_seconds < 90
    assert max(stage.target_vus for stage in plan.stages) <= 100
    assert {
        "X-TraceForge-Run-Id",
        "X-TraceForge-Phase",
        "X-TraceForge-Scenario",
        "X-TraceForge-Git-Sha",
    }.issubset(plan.required_headers)


def test_plan_rejects_missing_correlation_header() -> None:
    plan = create_plan(endpoint(), profile=Profile.QUICK, target_url="http://localhost:8099")
    value = plan.model_dump()
    del value["required_headers"]["X-TraceForge-Run-Id"]
    with pytest.raises(ValueError):
        LoadTestPlan.model_validate(value)


def test_renderer_is_deterministic_and_contains_no_arbitrary_source(tmp_path: Path) -> None:
    plan = create_plan(endpoint(), profile=Profile.QUICK, target_url="http://localhost:8099")
    first = render_script(plan, tmp_path / "first.js")
    second = render_script(plan, tmp_path / "second.js")
    assert first.script_digest == second.script_digest
    source = (tmp_path / "first.js").read_text(encoding="utf-8")
    assert "X-TraceForge-Run-Id" in source
    assert "ramping-vus" in source
    assert "eval(" not in source
