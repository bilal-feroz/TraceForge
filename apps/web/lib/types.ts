export type Stage =
  | "CREATED"
  | "REPOSITORY_VALIDATED"
  | "CHANGE_INSPECTED"
  | "ENDPOINTS_SCOPED"
  | "LOAD_PLAN_CREATED"
  | "K6_SCRIPT_VALIDATED"
  | "BASELINE_COMPLETED"
  | "CANDIDATE_COMPLETED"
  | "TELEMETRY_CONFIRMED"
  | "SIGNALS_CORRELATED"
  | "REGRESSION_CLASSIFIED"
  | "PATCH_PROPOSED"
  | "PATCH_AUDITED"
  | "PATCH_SANDBOXED"
  | "VERIFICATION_COMPLETED"
  | "VERDICT_PUBLISHED";

export type TerminalState = "PASSED" | "BLOCKED" | "NEEDS_REVIEW" | "FAILED" | "CANCELLED";

export interface MetricStats {
  count: number;
  rate: number;
  p50_ms: number;
  p90_ms: number;
  p95_ms: number;
  p99_ms: number;
  failure_rate: number;
  checks_passed: number;
  checks_failed: number;
  duration_seconds: number;
  threshold_failures: string[];
  ordered_p95_windows_ms: number[];
}

export interface Experiment {
  phase: "baseline" | "candidate" | "patched";
  window: {
    phase: string;
    started_at: string;
    ended_at: string;
  };
  exit_code: number;
  stats: MetricStats;
  script_digest: string;
  successful: boolean;
  error?: string | null;
}

export interface TraceEvidence {
  trace_id: string;
  span_id?: string | null;
  operation: string;
  duration_ms: number;
  status: string;
}

export interface LogEvidence {
  timestamp: string;
  body: string;
  severity: string;
  trace_id?: string | null;
}

export interface TelemetryEvidence {
  run_id: string;
  service_name: string;
  endpoint: string;
  available: boolean;
  window: {
    phase: string;
    started_at: string;
    ended_at: string;
  };
  traces: TraceEvidence[];
  logs: LogEvidence[];
  tools_discovered: string[];
  mcp_invocations: Array<{
    invocation_id: string;
    tool_name: string;
    duration_ms: number;
    success: boolean;
  }>;
  unavailable_reason?: string | null;
}

export interface RunSummary {
  run_id: string;
  stage: Stage;
  terminal_state?: TerminalState | null;
  created_at: string;
  updated_at: string;
  base_ref: string;
  candidate_ref: string;
  repository: string;
  verdict?: string | null;
  classification?: string | null;
  last_error?: string | null;
  telemetry: Partial<Record<"baseline" | "candidate" | "patched", { available: boolean }>>;
}

export interface Run {
  run_id: string;
  target: {
    path: string;
    base_ref: string;
    candidate_ref: string;
    target_url: string;
    profile: "quick" | "demo" | "full";
  };
  stage: Stage;
  terminal_state?: TerminalState | null;
  created_at: string;
  updated_at: string;
  endpoints: Array<{
    path: string;
    method: string;
    source_file: string;
    line: number;
    confidence: number;
    reason: string;
  }>;
  load_plan?: {
    endpoint: { path: string; method: string };
    scenario_name: string;
    profile: string;
    maximum_duration_seconds: number;
  } | null;
  experiments: Partial<Record<"baseline" | "candidate" | "patched", Experiment>>;
  telemetry: Partial<Record<"baseline" | "candidate" | "patched", TelemetryEvidence>>;
  assessment?: {
    classification: string;
    latency_p95: Delta;
    latency_p99: Delta;
    error_rate: Delta;
    throughput: Delta;
    implied_concurrency?: Delta | null;
    throughput_explained_by_latency?: boolean | null;
    latency_slope_ms_per_window?: number | null;
    threshold_violations: string[];
    deterministic_reasons: string[];
    sufficient_evidence: boolean;
    slow_span_concentration: Record<string, number>;
    error_concentration: Record<string, number>;
  } | null;
  diagnosis?: {
    summary: string;
    classification: string;
    affected_endpoint: string;
    likely_root_cause: string;
    root_cause_file?: string | null;
    confidence: number;
    supporting_metrics: string[];
    supporting_traces: string[];
    supporting_logs: string[];
    rejected_hypotheses: string[];
    remediation_strategy: string;
    unresolved_questions: string[];
    service_name: string;
    mcp_tools_used: string[];
  } | null;
  patch?: {
    unified_diff: string;
    explanation: string;
    changed_files: string[];
  } | null;
  patch_audit?: {
    passed: boolean;
    checks: Array<{ name: string; passed: boolean; detail: string }>;
    auditor: string;
  } | null;
  verification?: {
    status: string;
    tests_passed: boolean;
    telemetry_complete: boolean;
    same_script_digest: boolean;
    remaining_risks: string[];
  } | null;
  verdict?: {
    value: "SHIP" | "BLOCK" | "NEEDS_REVIEW";
    reason: string;
  } | null;
  last_error?: string | null;
}

export interface Delta {
  baseline: number;
  candidate: number;
  absolute: number;
  relative_percent?: number | null;
}

export type PhaseName = "baseline" | "candidate" | "patched";

export interface PhaseLoad {
  phase: PhaseName;
  successful: boolean;
  exit_code: number;
  request_count: number;
  throughput_rps: number;
  p50_ms: number;
  p90_ms: number;
  p95_ms: number;
  p99_ms: number;
  failure_rate: number;
  checks_passed: number;
  checks_failed: number;
  duration_seconds: number;
  threshold_failures: string[];
  ordered_p95_windows_ms: number[];
  script_digest: string;
  window: { phase: string; started_at: string; ended_at: string };
}

export interface PhaseEvidence {
  phase: PhaseName;
  available: boolean;
  unavailable_reason?: string | null;
  service_name: string;
  window: { phase: string; started_at: string; ended_at: string };
  trace_rows_retrieved: number;
  log_rows_retrieved: number;
  row_limit: number;
  row_limit_reached: boolean;
  spans_in_window: number;
  error_spans_in_window: number;
  logs_in_window: number;
  error_logs_in_window: number;
  lock_error_logs_in_window: number;
  http_status_counts: Record<string, number>;
  top_operations: Array<{ operation: string; span_count: number; p95_ms: number }>;
  metric_series: number;
  mcp_tool_calls: number;
  mcp_tool_failures: number;
  mcp_tools_used: string[];
  tools_discovered: number;
  trace_links: Array<{
    trace_id: string;
    span_id?: string | null;
    operation: string;
    duration_ms: number;
    status: string;
    error: boolean;
    signoz_url?: string | null;
  }>;
  log_samples: Array<{
    timestamp: string;
    severity: string;
    trace_id?: string | null;
    message: string;
    lock_error: boolean;
  }>;
}

export interface ComparisonMetric {
  key: string;
  label: string;
  unit: string;
  baseline?: number | null;
  candidate?: number | null;
  patched?: number | null;
  direction: "lower_is_better" | "higher_is_better" | "neutral";
  caveat?: string | null;
}

export interface ReleaseProof {
  run_id: string;
  generated_at: string;
  stage: Stage;
  terminal_state?: TerminalState | null;
  verdict?: "SHIP" | "BLOCK" | "NEEDS_REVIEW" | null;
  verdict_reason?: string | null;
  repository: string;
  base_ref: string;
  candidate_ref: string;
  base_sha?: string | null;
  candidate_sha?: string | null;
  merge_base_sha?: string | null;
  endpoint?: string | null;
  profile: string;
  scenario?: string | null;
  created_at: string;
  updated_at: string;
  elapsed_seconds: number;
  evidence_status: "confirmed" | "partial" | "unavailable" | "pending";
  classification?: string | null;
  patch_verification_status?: string | null;
  patch_audit_passed?: boolean | null;
  patch_changed_files: string[];
  phases: Array<{ phase: PhaseName; load?: PhaseLoad | null; evidence?: PhaseEvidence | null }>;
  comparison: ComparisonMetric[];
  interpretation: string[];
  timeline: Array<{
    sequence: number;
    action: string;
    previous_state: string;
    next_state: string;
    occurred_at: string;
    outcome: string;
    elapsed_seconds: number;
    event_hash_prefix: string;
  }>;
  ledger: {
    recorded: boolean;
    valid: boolean;
    event_count: number;
    terminal_state?: string | null;
    terminal_required: boolean;
    head_hash_prefix?: string | null;
    errors: string[];
  };
  signoz_service?: string | null;
  limitations: string[];
}

