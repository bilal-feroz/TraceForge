from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Stage(StrEnum):
    CREATED = "CREATED"
    REPOSITORY_VALIDATED = "REPOSITORY_VALIDATED"
    CHANGE_INSPECTED = "CHANGE_INSPECTED"
    ENDPOINTS_SCOPED = "ENDPOINTS_SCOPED"
    LOAD_PLAN_CREATED = "LOAD_PLAN_CREATED"
    K6_SCRIPT_VALIDATED = "K6_SCRIPT_VALIDATED"
    BASELINE_COMPLETED = "BASELINE_COMPLETED"
    CANDIDATE_COMPLETED = "CANDIDATE_COMPLETED"
    TELEMETRY_CONFIRMED = "TELEMETRY_CONFIRMED"
    SIGNALS_CORRELATED = "SIGNALS_CORRELATED"
    REGRESSION_CLASSIFIED = "REGRESSION_CLASSIFIED"
    PATCH_PROPOSED = "PATCH_PROPOSED"
    PATCH_AUDITED = "PATCH_AUDITED"
    PATCH_SANDBOXED = "PATCH_SANDBOXED"
    VERIFICATION_COMPLETED = "VERIFICATION_COMPLETED"
    VERDICT_PUBLISHED = "VERDICT_PUBLISHED"


class TerminalState(StrEnum):
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Phase(StrEnum):
    BASELINE = "baseline"
    CANDIDATE = "candidate"
    PATCHED = "patched"


class Profile(StrEnum):
    QUICK = "quick"
    DEMO = "demo"
    FULL = "full"


class RegressionClassification(StrEnum):
    NO_REGRESSION = "NO_REGRESSION"
    ERROR_RATE_REGRESSION = "ERROR_RATE_REGRESSION"
    LATENCY_REGRESSION = "LATENCY_REGRESSION"
    THROUGHPUT_REGRESSION = "THROUGHPUT_REGRESSION"
    DATABASE_CONTENTION = "DATABASE_CONTENTION"
    DEPENDENCY_REGRESSION = "DEPENDENCY_REGRESSION"
    RESOURCE_SATURATION = "RESOURCE_SATURATION"
    SILENT_DEGRADATION = "SILENT_DEGRADATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class PatchVerificationStatus(StrEnum):
    VERIFIED_IMPROVEMENT = "VERIFIED_IMPROVEMENT"
    VERIFIED_NO_CHANGE = "VERIFIED_NO_CHANGE"
    VERIFIED_REGRESSION = "VERIFIED_REGRESSION"
    TESTS_FAILED = "TESTS_FAILED"
    TELEMETRY_INCOMPLETE = "TELEMETRY_INCOMPLETE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class VerdictValue(StrEnum):
    SHIP = "SHIP"
    BLOCK = "BLOCK"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class RepositoryTarget(StrictModel):
    path: Path
    base_ref: str = Field(min_length=1, max_length=256)
    candidate_ref: str = Field(min_length=1, max_length=256)
    target_url: HttpUrl
    profile: Profile = Profile.DEMO
    target_command: list[str] | None = None


class GitRevision(StrictModel):
    ref: str
    sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    subject: str
    author_time: datetime


class ChangedFile(StrictModel):
    path: str
    status: str
    additions: int = 0
    deletions: int = 0


class ChangeSet(StrictModel):
    base: GitRevision
    candidate: GitRevision
    merge_base_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    files: list[ChangedFile]
    unified_diff: str
    diff_digest: str


class AffectedEndpoint(StrictModel):
    path: str = Field(pattern=r"^/")
    method: str
    source_file: str
    line: int = Field(ge=1)
    confidence: float = Field(ge=0, le=1)
    reason: str
    request_body_example: dict[str, Any] | list[Any] | str | int | float | bool | None = None

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        method = value.upper()
        allowed = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        if method not in allowed:
            raise ValueError(f"unsupported HTTP method: {method}")
        return method


class LoadStage(StrictModel):
    duration_seconds: int = Field(ge=1, le=300)
    target_vus: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1, max_length=300)


class LoadCheck(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    expression: Literal["status_expected", "latency_below"]
    value: float | int | None = None


class LoadThreshold(StrictModel):
    metric: Literal["http_req_failed", "http_req_duration", "checks"]
    expression: str = Field(min_length=1, max_length=100)
    abort_on_fail: bool = False
    delay_abort_seconds: int = Field(default=0, ge=0, le=60)


class LoadTestPlan(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    endpoint: AffectedEndpoint
    scenario_name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    scenario_type: Literal["ramping-vus"] = "ramping-vus"
    profile: Profile
    request_body_template: dict[str, Any] | list[Any] | str | int | float | bool | None
    required_headers: dict[str, str]
    setup_requirements: list[str] = Field(default_factory=list, max_length=10)
    warmup_seconds: int = Field(ge=0, le=30)
    stages: list[LoadStage] = Field(min_length=1, max_length=8)
    checks: list[LoadCheck] = Field(min_length=1, max_length=10)
    thresholds: list[LoadThreshold] = Field(min_length=1, max_length=10)
    maximum_duration_seconds: int = Field(ge=1, le=600)
    expected_response_codes: list[int] = Field(min_length=1, max_length=10)
    cleanup_requirements: list[str] = Field(default_factory=list, max_length=10)
    deterministic_seed: int = Field(default=1729, ge=0, le=2**31 - 1)

    @model_validator(mode="after")
    def validate_budget(self) -> LoadTestPlan:
        stage_duration = sum(stage.duration_seconds for stage in self.stages)
        if stage_duration + self.warmup_seconds > self.maximum_duration_seconds:
            raise ValueError("warmup plus stage duration exceeds maximum duration")
        required = {
            "X-TraceForge-Run-Id",
            "X-TraceForge-Phase",
            "X-TraceForge-Scenario",
            "X-TraceForge-Git-Sha",
        }
        if not required.issubset(self.required_headers):
            raise ValueError("all TraceForge correlation headers are required")
        return self


class GeneratedK6Script(StrictModel):
    plan_digest: str
    script_path: Path
    script_digest: str
    k6_version: str | None = None
    validated: bool = False
    validation_error: str | None = None


class ExperimentWindow(StrictModel):
    phase: Phase
    started_at: datetime
    ended_at: datetime

    @model_validator(mode="after")
    def chronological(self) -> ExperimentWindow:
        if self.ended_at < self.started_at:
            raise ValueError("experiment window ends before it starts")
        return self


class MetricStats(StrictModel):
    count: int = Field(ge=0)
    rate: float = Field(ge=0)
    p50_ms: float = Field(ge=0)
    p90_ms: float = Field(ge=0)
    p95_ms: float = Field(ge=0)
    p99_ms: float = Field(ge=0)
    failure_rate: float = Field(ge=0, le=1)
    checks_passed: int = Field(ge=0)
    checks_failed: int = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    threshold_failures: list[str] = Field(default_factory=list)
    ordered_p95_windows_ms: list[float] = Field(default_factory=list)


class K6RunResult(StrictModel):
    phase: Phase
    window: ExperimentWindow
    exit_code: int
    stats: MetricStats
    summary_path: Path
    raw_output_path: Path
    script_digest: str
    successful: bool
    error: str | None = None


class TraceEvidence(StrictModel):
    trace_id: str
    span_id: str | None = None
    operation: str
    duration_ms: float = Field(ge=0)
    status: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class LogEvidence(StrictModel):
    timestamp: datetime
    body: str
    severity: str
    trace_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class MetricEvidence(StrictModel):
    name: str
    unit: str | None = None
    points: list[tuple[datetime, float]]
    attributes: dict[str, Any] = Field(default_factory=dict)


class MCPInvocation(StrictModel):
    invocation_id: str
    tool_name: str
    started_at: datetime
    duration_ms: float = Field(ge=0)
    request_digest: str
    sanitized_request: dict[str, Any]
    response_digest: str | None = None
    response_summary: str | None = None
    success: bool
    error: str | None = None


class TelemetryEvidence(StrictModel):
    run_id: str
    service_name: str
    window: ExperimentWindow
    endpoint: str
    available: bool
    traces: list[TraceEvidence] = Field(default_factory=list)
    logs: list[LogEvidence] = Field(default_factory=list)
    metrics: list[MetricEvidence] = Field(default_factory=list)
    mcp_invocations: list[MCPInvocation] = Field(default_factory=list)
    tools_discovered: list[str] = Field(default_factory=list)
    unavailable_reason: str | None = None


class NumericDelta(StrictModel):
    baseline: float
    candidate: float
    absolute: float
    relative_percent: float | None


class RegressionAssessment(StrictModel):
    classification: RegressionClassification
    latency_p95: NumericDelta
    latency_p99: NumericDelta
    error_rate: NumericDelta
    throughput: NumericDelta
    implied_concurrency: NumericDelta | None = None
    throughput_explained_by_latency: bool | None = None
    latency_slope_ms_per_window: float | None
    server_client_latency_gap_ms: float | None
    threshold_violations: list[str]
    slow_span_concentration: dict[str, float] = Field(default_factory=dict)
    error_concentration: dict[str, int] = Field(default_factory=dict)
    deterministic_reasons: list[str]
    sufficient_evidence: bool


class Diagnosis(StrictModel):
    summary: str
    classification: RegressionClassification
    affected_endpoint: str
    first_bad_revision: str
    likely_root_cause: str
    root_cause_file: str | None = None
    root_cause_lines: list[int] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    supporting_metrics: list[str]
    supporting_traces: list[str]
    supporting_logs: list[str]
    rejected_hypotheses: list[str]
    remediation_strategy: str
    unresolved_questions: list[str]
    evidence_window: ExperimentWindow
    service_name: str
    mcp_tools_used: list[str]


class PatchProposal(StrictModel):
    unified_diff: str
    explanation: str
    changed_files: list[str]
    diagnosis_digest: str
    reversible: bool = True


class AuditCheck(StrictModel):
    name: str
    passed: bool
    detail: str


class PatchAudit(StrictModel):
    passed: bool
    checks: list[AuditCheck]
    auditor: str
    audited_at: datetime = Field(default_factory=utc_now)


class VerificationResult(StrictModel):
    status: PatchVerificationStatus
    baseline: K6RunResult
    candidate: K6RunResult
    patched: K6RunResult | None
    assessment: RegressionAssessment | None
    tests_passed: bool
    telemetry_complete: bool
    same_script_digest: bool
    remaining_risks: list[str]


class Verdict(StrictModel):
    value: VerdictValue
    reason: str
    published_at: datetime = Field(default_factory=utc_now)
    verification_status: PatchVerificationStatus | None = None


class StateTransition(StrictModel):
    event_id: str
    run_id: str
    previous_state: Stage | TerminalState
    next_state: Stage | TerminalState
    action: str
    occurred_at: datetime = Field(default_factory=utc_now)
    outcome: Literal["success", "failure", "skipped"]


class LedgerEvent(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    sequence: int = Field(ge=1)
    timestamp: datetime
    previous_state: str
    next_state: str
    action: str
    actor_type: Literal["system", "agent", "user", "tool"]
    actor_name: str
    tool_name: str | None = None
    input_digest: str
    output_digest: str
    evidence_ids: list[str] = Field(default_factory=list)
    previous_hash: str
    event_hash: str
    outcome: Literal["success", "failure", "skipped"]
    error: str | None = None


class TraceForgeRun(StrictModel):
    run_id: str
    target: RepositoryTarget
    stage: Stage
    terminal_state: TerminalState | None = None
    created_at: datetime
    updated_at: datetime
    change_set: ChangeSet | None = None
    endpoints: list[AffectedEndpoint] = Field(default_factory=list)
    load_plan: LoadTestPlan | None = None
    k6_script: GeneratedK6Script | None = None
    experiments: dict[Phase, K6RunResult] = Field(default_factory=dict)
    telemetry: dict[Phase, TelemetryEvidence] = Field(default_factory=dict)
    assessment: RegressionAssessment | None = None
    diagnosis: Diagnosis | None = None
    patch: PatchProposal | None = None
    patch_audit: PatchAudit | None = None
    verification: VerificationResult | None = None
    verdict: Verdict | None = None
    last_error: str | None = None


class RunCreateRequest(StrictModel):
    repository: str
    base_ref: str
    candidate_ref: str
    target_url: HttpUrl
    profile: Profile = Profile.DEMO


class SSEEvent(StrictModel):
    event: str
    data: dict[str, Any]
