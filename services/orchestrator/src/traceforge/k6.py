from __future__ import annotations

import hashlib
import json
import math
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from traceforge.ledger import canonical_json
from traceforge.models import (
    ExperimentWindow,
    GeneratedK6Script,
    K6RunResult,
    LoadTestPlan,
    MetricStats,
    Phase,
)
from traceforge.process import ProcessError, run_process
from traceforge.settings import Settings


class K6Unavailable(RuntimeError):
    pass


def _js(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def render_script(plan: LoadTestPlan, path: Path) -> GeneratedK6Script:
    stages = [
        {"duration": f"{stage.duration_seconds}s", "target": stage.target_vus}
        for stage in plan.stages
    ]
    thresholds: dict[str, list[Any]] = {}
    for threshold in plan.thresholds:
        entry: Any = threshold.expression
        if threshold.abort_on_fail:
            entry = {
                "threshold": threshold.expression,
                "abortOnFail": True,
                "delayAbortEval": f"{threshold.delay_abort_seconds}s",
            }
        thresholds.setdefault(threshold.metric, []).append(entry)
    expected = plan.expected_response_codes
    payload = (
        "null"
        if plan.request_body_template is None
        else f"JSON.stringify({_js(plan.request_body_template)})"
    )
    content = f"""// Generated deterministically by TraceForge. Do not edit during a run.
import http from 'k6/http';
import {{ check }} from 'k6';

export const options = {{
  scenarios: {{
    {_js(plan.scenario_name)}: {{
      executor: 'ramping-vus',
      startVUs: 0,
      gracefulRampDown: '5s',
      stages: {_js(stages)},
      tags: {{ traceforge_scenario: {_js(plan.scenario_name)} }},
    }},
  }},
  thresholds: {_js(thresholds)},
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
  userAgent: 'TraceForge/0.1 k6',
}};

const target = (__ENV.TARGET_URL || '').replace(/\\/$/, '');
const headers = {{
  'Content-Type': 'application/json',
  'X-TraceForge-Run-Id': __ENV.TRACEFORGE_RUN_ID,
  'X-TraceForge-Phase': __ENV.TRACEFORGE_PHASE,
  'X-TraceForge-Scenario': {_js(plan.scenario_name)},
  'X-TraceForge-Git-Sha': __ENV.TRACEFORGE_GIT_SHA,
}};
const expectedStatuses = {_js(expected)};

export function setup() {{
  if (!target || !__ENV.TRACEFORGE_RUN_ID || !__ENV.TRACEFORGE_PHASE ||
      !__ENV.TRACEFORGE_GIT_SHA) {{
    throw new Error('TraceForge correlation environment is incomplete');
  }}
  return {{ target }};
}}

export default function (data) {{
  const url = data.target + {_js(plan.endpoint.path)};
  const response = http.request({_js(plan.endpoint.method)}, url, {payload}, {{
    headers,
    tags: {{
      traceforge_run_id: __ENV.TRACEFORGE_RUN_ID,
      traceforge_phase: __ENV.TRACEFORGE_PHASE,
      traceforge_scenario: {_js(plan.scenario_name)},
      endpoint: {_js(plan.endpoint.path)},
    }},
    timeout: '10s',
  }});
  check(response, {{
    'expected status': (r) => expectedStatuses.includes(r.status),
    'request below 2s': (r) => r.timings.duration < 2000,
  }});
}}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    plan_digest = hashlib.sha256(canonical_json(plan.model_dump(mode="json")).encode()).hexdigest()
    script_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return GeneratedK6Script(
        plan_digest=plan_digest,
        script_path=path,
        script_digest=script_digest,
    )


def k6_version(settings: Settings) -> str:
    if shutil.which("k6") is None:
        raise K6Unavailable("k6 is not installed; install k6 v2 or later and rerun doctor")
    result = run_process(
        ["k6", "version"],
        timeout_seconds=15,
        max_output_bytes=settings.max_subprocess_output_bytes,
    )
    return result.stdout.strip() or result.stderr.strip()


def validate_script(script: GeneratedK6Script, settings: Settings) -> GeneratedK6Script:
    try:
        version = k6_version(settings)
        run_process(
            ["k6", "inspect", str(script.script_path)],
            timeout_seconds=30,
            max_output_bytes=settings.max_subprocess_output_bytes,
        )
    except (K6Unavailable, ProcessError) as exc:
        return script.model_copy(
            update={"validated": False, "validation_error": str(exc), "k6_version": None}
        )
    return script.model_copy(
        update={"validated": True, "validation_error": None, "k6_version": version}
    )


def _values(metric: Any) -> dict[str, Any]:
    if not isinstance(metric, dict):
        return {}
    values = metric.get("values")
    if isinstance(values, dict):
        return values
    return metric


def _number(values: dict[str, Any], *names: str, default: float = 0.0) -> float:
    for name in names:
        value = values.get(name)
        if isinstance(value, int | float) and math.isfinite(float(value)):
            return float(value)
    return default


def _ordered_windows(raw_json_path: Path, *, bucket_seconds: int = 10) -> list[float]:
    if not raw_json_path.exists():
        return []
    buckets: dict[int, list[float]] = {}
    first_timestamp: float | None = None
    for line in raw_json_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("type") != "Point" or item.get("metric") != "http_req_duration":
            continue
        data = item.get("data", {})
        value = data.get("value")
        time_text = data.get("time")
        if not isinstance(value, int | float) or not isinstance(time_text, str):
            continue
        try:
            timestamp = datetime.fromisoformat(time_text.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if first_timestamp is None:
            first_timestamp = timestamp
        bucket = int((timestamp - first_timestamp) // bucket_seconds)
        buckets.setdefault(bucket, []).append(float(value))
    percentiles: list[float] = []
    for bucket in sorted(buckets):
        values = sorted(buckets[bucket])
        if not values:
            continue
        index = min(len(values) - 1, math.ceil(len(values) * 0.95) - 1)
        percentiles.append(values[index])
    return percentiles


def parse_summary(
    summary_path: Path,
    *,
    raw_json_path: Path,
    duration_seconds: float,
) -> MetricStats:
    document = json.loads(summary_path.read_text(encoding="utf-8"))
    metrics = document.get("metrics", document.get("metric", {}))
    if not isinstance(metrics, dict):
        raise ValueError("k6 summary has no metrics object")
    duration = _values(metrics.get("http_req_duration"))
    failures = _values(metrics.get("http_req_failed"))
    requests = _values(metrics.get("http_reqs"))
    checks = _values(metrics.get("checks"))
    count = int(_number(requests, "count"))
    failure_rate = _number(failures, "rate", "value")
    check_passes = int(_number(checks, "passes", "pass_count"))
    check_fails = int(_number(checks, "fails", "fail_count"))
    throughput = _number(
        requests, "rate", default=count / duration_seconds if duration_seconds else 0
    )
    threshold_failures: list[str] = []
    for metric_name, metric in metrics.items():
        if not isinstance(metric, dict):
            continue
        thresholds = metric.get("thresholds", {})
        if isinstance(thresholds, dict):
            for expression, result in thresholds.items():
                if isinstance(result, dict) and result.get("ok") is False:
                    threshold_failures.append(f"{metric_name}: {expression}")
                elif result is True:
                    threshold_failures.append(f"{metric_name}: {expression}")
    return MetricStats(
        count=count,
        rate=max(0, throughput),
        p50_ms=max(0, _number(duration, "med", "p(50)", "p50")),
        p90_ms=max(0, _number(duration, "p(90)", "p90")),
        p95_ms=max(0, _number(duration, "p(95)", "p95")),
        p99_ms=max(0, _number(duration, "p(99)", "p99")),
        failure_rate=min(1, max(0, failure_rate)),
        checks_passed=max(0, check_passes),
        checks_failed=max(0, check_fails),
        duration_seconds=max(0, duration_seconds),
        threshold_failures=threshold_failures,
        ordered_p95_windows_ms=_ordered_windows(raw_json_path),
    )


def execute(
    *,
    script: GeneratedK6Script,
    phase: Phase,
    run_id: str,
    git_sha: str,
    target_url: str,
    artifact_dir: Path,
    settings: Settings,
) -> K6RunResult:
    if not script.validated:
        raise K6Unavailable(script.validation_error or "k6 script was not validated")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary_path = artifact_dir / "summary.json"
    raw_json_path = artifact_dir / "samples.json"
    output_path = artifact_dir / "k6-output.log"
    started = datetime.now(UTC)
    result = run_process(
        [
            "k6",
            "run",
            "--summary-export",
            str(summary_path),
            "--out",
            f"json={raw_json_path}",
            str(script.script_path),
        ],
        env={
            "TARGET_URL": target_url,
            "TRACEFORGE_RUN_ID": run_id,
            "TRACEFORGE_PHASE": phase.value,
            "TRACEFORGE_GIT_SHA": git_sha,
        },
        timeout_seconds=settings.subprocess_timeout_seconds,
        max_output_bytes=settings.max_subprocess_output_bytes,
        check=False,
    )
    ended = datetime.now(UTC)
    output_path.write_text(
        result.stdout + ("\n" if result.stdout and result.stderr else "") + result.stderr,
        encoding="utf-8",
    )
    duration = (ended - started).total_seconds()
    if not summary_path.exists():
        empty = MetricStats(
            count=0,
            rate=0,
            p50_ms=0,
            p90_ms=0,
            p95_ms=0,
            p99_ms=0,
            failure_rate=1,
            checks_passed=0,
            checks_failed=0,
            duration_seconds=duration,
            threshold_failures=["k6 did not produce a summary"],
        )
        return K6RunResult(
            phase=phase,
            window=ExperimentWindow(phase=phase, started_at=started, ended_at=ended),
            exit_code=result.returncode,
            stats=empty,
            summary_path=summary_path,
            raw_output_path=output_path,
            script_digest=script.script_digest,
            successful=False,
            error="k6 did not produce a summary",
        )
    stats = parse_summary(summary_path, raw_json_path=raw_json_path, duration_seconds=duration)
    return K6RunResult(
        phase=phase,
        window=ExperimentWindow(phase=phase, started_at=started, ended_at=ended),
        exit_code=result.returncode,
        stats=stats,
        summary_path=summary_path,
        raw_output_path=output_path,
        script_digest=script.script_digest,
        successful=result.returncode == 0 and not stats.threshold_failures,
        error=None if result.returncode == 0 else f"k6 exited {result.returncode}",
    )
