from __future__ import annotations

from traceforge.models import TraceForgeRun


def render_report(run: TraceForgeRun) -> str:
    lines = [
        f"# TraceForge evidence report — {run.run_id}",
        "",
        f"- Stage: `{run.stage.value}`",
        f"- Terminal state: `{run.terminal_state.value if run.terminal_state else 'active'}`",
        f"- Repository: `{run.target.path}`",
        f"- Revisions: `{run.target.base_ref}` → `{run.target.candidate_ref}`",
        f"- Created: {run.created_at.isoformat()}",
        "",
    ]
    if run.load_plan:
        lines.extend(
            [
                "## Experiment",
                "",
                f"- Endpoint: `{run.load_plan.endpoint.method} {run.load_plan.endpoint.path}`",
                f"- Profile: `{run.load_plan.profile.value}`",
                f"- Scenario: `{run.load_plan.scenario_name}`",
                "",
            ]
        )
    if run.assessment:
        assessment = run.assessment
        lines.extend(
            [
                "## Deterministic assessment",
                "",
                f"- Classification: `{assessment.classification.value}`",
                f"- P95: {assessment.latency_p95.baseline:.2f} ms → "
                f"{assessment.latency_p95.candidate:.2f} ms",
                f"- Error rate: {assessment.error_rate.baseline:.4f} → "
                f"{assessment.error_rate.candidate:.4f}",
                f"- Throughput: {assessment.throughput.baseline:.2f} → "
                f"{assessment.throughput.candidate:.2f} req/s",
                "",
            ]
        )
    lines.extend(["## SigNoz evidence", ""])
    for phase, evidence in run.telemetry.items():
        lines.extend(
            [
                f"### {phase.value}",
                "",
                f"- Window: {evidence.window.started_at.isoformat()} → "
                f"{evidence.window.ended_at.isoformat()}",
                f"- Service: `{evidence.service_name}`",
                f"- Available: `{str(evidence.available).lower()}`",
                f"- Trace IDs: {', '.join(trace.trace_id for trace in evidence.traces[:10]) or 'none'}",
                f"- MCP tools: "
                f"{', '.join(sorted({call.tool_name for call in evidence.mcp_invocations})) or 'none'}",
                (
                    f"- Unavailable reason: {evidence.unavailable_reason}"
                    if evidence.unavailable_reason
                    else ""
                ),
                "",
            ]
        )
    if run.verdict:
        lines.extend(
            [
                "## Verdict",
                "",
                f"**{run.verdict.value.value}** — {run.verdict.reason}",
                "",
            ]
        )
    lines.extend(
        [
            "This report distinguishes measured evidence from unavailable integrations. "
            "It contains no synthetic SigNoz responses.",
            "",
        ]
    )
    return "\n".join(line for line in lines if line is not None)
