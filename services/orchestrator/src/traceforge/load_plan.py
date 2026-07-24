from __future__ import annotations

from urllib.parse import urlparse

from traceforge.models import (
    AffectedEndpoint,
    LoadCheck,
    LoadStage,
    LoadTestPlan,
    LoadThreshold,
    Profile,
)


class LoadPlanError(ValueError):
    pass


def choose_endpoint(endpoints: list[AffectedEndpoint]) -> AffectedEndpoint:
    if not endpoints:
        raise LoadPlanError("no affected API endpoint was discovered")
    write_methods = {"POST": 0, "PUT": 1, "PATCH": 2, "GET": 3, "DELETE": 4}
    return sorted(
        endpoints,
        key=lambda item: (write_methods.get(item.method, 5), -item.confidence, item.path),
    )[0]


def stages_for(profile: Profile) -> tuple[int, list[LoadStage], int]:
    if profile == Profile.QUICK:
        stages = [
            LoadStage(duration_seconds=4, target_vus=2, reason="establish a low-load signal"),
            LoadStage(duration_seconds=8, target_vus=8, reason="exercise bounded concurrency"),
            LoadStage(duration_seconds=4, target_vus=0, reason="drain in-flight requests"),
        ]
        return 2, stages, 20
    if profile == Profile.DEMO:
        stages = [
            LoadStage(
                duration_seconds=8, target_vus=4, reason="establish a stable low-load window"
            ),
            LoadStage(
                duration_seconds=15, target_vus=16, reason="surface concurrency-sensitive faults"
            ),
            LoadStage(duration_seconds=20, target_vus=32, reason="measure sustained pressure"),
            LoadStage(duration_seconds=10, target_vus=8, reason="observe recovery behavior"),
            LoadStage(duration_seconds=5, target_vus=0, reason="drain in-flight requests"),
        ]
        return 3, stages, 61
    stages = [
        LoadStage(duration_seconds=15, target_vus=5, reason="capture a stable initial window"),
        LoadStage(duration_seconds=30, target_vus=25, reason="apply moderate concurrency"),
        LoadStage(duration_seconds=45, target_vus=50, reason="measure sustained peak behavior"),
        LoadStage(duration_seconds=30, target_vus=75, reason="probe high-load behavior"),
        LoadStage(duration_seconds=15, target_vus=0, reason="measure recovery"),
    ]
    return 5, stages, 140


def create_plan(
    endpoint: AffectedEndpoint,
    *,
    profile: Profile,
    target_url: str,
) -> LoadTestPlan:
    parsed = urlparse(target_url)
    if not parsed.hostname:
        raise LoadPlanError("target URL is invalid")
    warmup, stages, maximum = stages_for(profile)
    body = endpoint.request_body_example
    if endpoint.method in {"POST", "PUT", "PATCH"} and not body:
        body = {"name": "traceforge", "value": 1}
    return LoadTestPlan(
        endpoint=endpoint,
        scenario_name="affected_endpoint",
        profile=profile,
        request_body_template=body,
        required_headers={
            "Content-Type": "application/json",
            "X-TraceForge-Run-Id": "${RUN_ID}",
            "X-TraceForge-Phase": "${PHASE}",
            "X-TraceForge-Scenario": "${SCENARIO}",
            "X-TraceForge-Git-Sha": "${GIT_SHA}",
        },
        warmup_seconds=warmup,
        stages=stages,
        checks=[
            LoadCheck(name="expected status", expression="status_expected"),
            LoadCheck(name="request below 2s", expression="latency_below", value=2_000),
        ],
        thresholds=[
            LoadThreshold(metric="http_req_failed", expression="rate<0.05"),
            LoadThreshold(metric="http_req_duration", expression="p(95)<1000"),
            LoadThreshold(metric="checks", expression="rate>0.95"),
        ],
        maximum_duration_seconds=maximum,
        expected_response_codes=[200, 201, 202, 204],
        cleanup_requirements=[],
    )
