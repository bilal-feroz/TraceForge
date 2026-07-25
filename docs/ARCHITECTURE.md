# TraceForge architecture

TraceForge is a deterministic reliability workflow with an observability-backed evidence boundary.
Language-model integration is optional; it cannot advance state, classify a regression, authorize a
patch, or publish a verdict.

## 1. System context

```mermaid
flowchart LR
  U[Engineer / reviewer] --> CLI[TraceForge CLI]
  U --> WEB[Next.js Control Room]
  WEB --> API[FastAPI orchestrator]
  CLI --> ENG[Run engine]
  API --> ENG
  ENG --> GIT[(Local Git repository)]
  ENG --> K6[k6 v2]
  K6 --> APP[Instrumented target]
  APP --> OTLP[OTLP ingestion]
  ENG --> OTLP
  OTLP --> SZ[(SigNoz)]
  ENG <-->|MCP Streamable HTTP| MCP[SigNoz MCP]
  MCP --> SZ
  ENG --> STORE[(SQLite + artifacts)]
  ENG --> LEDGER[(Hash-chained ledger)]
```

The API never accepts a startup command. Local code execution is available only from the CLI when
`TRACEFORGE_TRUSTED_LOCAL_MODE=true`, the repository resolves beneath an allowlisted root, and the
target host is allowlisted.

## 2. Deterministic state machine

```mermaid
stateDiagram-v2
  [*] --> CREATED
  CREATED --> REPOSITORY_VALIDATED
  REPOSITORY_VALIDATED --> CHANGE_INSPECTED
  CHANGE_INSPECTED --> ENDPOINTS_SCOPED
  ENDPOINTS_SCOPED --> LOAD_PLAN_CREATED
  LOAD_PLAN_CREATED --> K6_SCRIPT_VALIDATED
  K6_SCRIPT_VALIDATED --> BASELINE_COMPLETED
  BASELINE_COMPLETED --> CANDIDATE_COMPLETED
  CANDIDATE_COMPLETED --> TELEMETRY_CONFIRMED: exact-window evidence exists
  CANDIDATE_COMPLETED --> VERDICT_PUBLISHED: telemetry unavailable
  TELEMETRY_CONFIRMED --> SIGNALS_CORRELATED
  SIGNALS_CORRELATED --> REGRESSION_CLASSIFIED
  REGRESSION_CLASSIFIED --> PATCH_PROPOSED: material regression
  REGRESSION_CLASSIFIED --> VERIFICATION_COMPLETED: control
  REGRESSION_CLASSIFIED --> VERDICT_PUBLISHED: insufficient evidence
  PATCH_PROPOSED --> PATCH_AUDITED
  PATCH_AUDITED --> PATCH_SANDBOXED: audit passes
  PATCH_AUDITED --> VERDICT_PUBLISHED: audit fails
  PATCH_SANDBOXED --> VERIFICATION_COMPLETED
  VERIFICATION_COMPLETED --> VERDICT_PUBLISHED
  VERDICT_PUBLISHED --> PASSED
  VERDICT_PUBLISHED --> BLOCKED
  VERDICT_PUBLISHED --> NEEDS_REVIEW
  CREATED --> CANCELLED
  REPOSITORY_VALIDATED --> FAILED
```

Every transition has a stable event ID. SQLite enforces idempotency and the ledger records the
previous state, next state, actor, action, input/output digests, evidence IDs, prior hash, and event
hash. Replaying the same transition does not append a second event.

## 3. Experiment sequence

```mermaid
sequenceDiagram
  participant E as Run engine
  participant G as Git/worktree
  participant T as Target
  participant K as k6
  participant O as OTLP/SigNoz
  participant M as SigNoz MCP

  E->>G: inspect base...candidate diff
  E->>G: detached worktree at base SHA
  E->>T: start base with service.version=base SHA
  E->>K: run validated script with phase=baseline
  K->>T: bounded requests + correlation headers
  T-->>O: traces, logs, metrics
  K-->>E: raw output + machine summary
  E->>G: remove base worktree
  E->>G: detached worktree at candidate SHA
  E->>T: start candidate with service.version=candidate SHA
  E->>K: run identical script with phase=candidate
  T-->>O: traces, logs, metrics
  K-->>E: raw output + machine summary
  E->>M: query exact windows and run ID
  M-->>E: retrieved server-side evidence
```

The generated script is a pure compilation of a validated `LoadTestPlan`. The same script digest is
required for baseline, candidate, and patched phases. Profiles impose hard VU and time budgets.

## 4. Evidence and decision flow

```mermaid
flowchart TD
  C[k6 client metrics] --> CORR[Correlation]
  T[SigNoz traces] --> CORR
  L[SigNoz logs] --> CORR
  M[SigNoz metrics] --> CORR
  O[Service and top operations] --> CORR
  A[Attribute-key/value discovery] --> CORR
  CORR --> DET[Deterministic assessment]
  DET -->|sufficient + regression| D[Evidence-grounded diagnosis]
  DET -->|sufficient + no regression| CTRL[Control verification]
  DET -->|missing server evidence| NR[NEEDS_REVIEW]
  D --> P[Scoped patch proposal]
  P --> AUDIT[Independent deterministic audit]
  AUDIT --> PROOF[Sandbox proof]
  PROOF --> V{Verdict gates}
  V --> SHIP[SHIP]
  V --> BLOCK[BLOCK]
  V --> NR
```

Client measurements alone never count as sufficient evidence. Missing credentials, a missing
service, absent correlated traces, an ingestion timeout, MCP schema drift, or a required tool
failure all produce the explicit message `SigNoz verification unavailable`.

## 5. Patch sandbox and proof

```mermaid
flowchart LR
  DX[Diagnosis + evidence IDs] --> REV[Minimal reversion diff]
  REV --> SCOPE{Changed files only?}
  SCOPE -->|no| REJECT[Reject]
  SCOPE -->|yes| CHECK[git apply --check]
  CHECK --> GROUND{SigNoz grounded?}
  GROUND -->|no| REVIEW[NEEDS_REVIEW]
  GROUND -->|yes| WT[Detached managed worktree]
  WT --> APPLY[git apply]
  APPLY --> TEST[Target tests]
  TEST --> LOAD[Same k6 script]
  LOAD --> QUERY[New SigNoz window]
  QUERY --> GATES{Tests + thresholds + improvement + telemetry}
  GATES -->|all pass| SHIP[SHIP]
  GATES -->|regression / tests fail| BLOCK[BLOCK]
  GATES -->|incomplete| REVIEW
```

The source checkout is not mutated. Patch application and cleanup are constrained to the run's
managed worktree directory. Patch text is rejected if it touches files outside the original change
set or contains credential-like material.

## 6. Trust and deployment boundaries

```mermaid
flowchart TB
  subgraph Browser["Untrusted browser boundary"]
    UI[Control Room]
  end
  subgraph Orchestrator["TraceForge process"]
    API[Versioned API + SSE]
    POLICY[Allowlist / limits / state gates]
    ENGINE[Engine]
    DATA[(Local run data)]
  end
  subgraph Sandbox["Managed execution boundary"]
    WT[Detached worktree]
    TARGET[Target process]
    K6[k6]
  end
  subgraph External["External control and data planes"]
    INGEST[SigNoz OTLP ingestion]
    MCP[SigNoz MCP endpoint]
  end

  UI -->|typed JSON, no commands| API
  API --> POLICY --> ENGINE
  ENGINE --> DATA
  ENGINE -->|argument arrays, timeouts| Sandbox
  TARGET -->|telemetry only| INGEST
  ENGINE -->|workflow telemetry| INGEST
  ENGINE -->|read-only investigation calls| MCP
  MCP -->|untrusted structured output| POLICY
```

## Components and durable data

| Component | Responsibility | Durable output |
| --- | --- | --- |
| `traceforge.engine` | Legal workflow orchestration and verdict gates | Serialized `TraceForgeRun` |
| `traceforge.git_inspector` | Revision validation, merge base, diff metadata | `change.diff`, change digest |
| `traceforge.endpoints` | Changed-hunk-aware FastAPI endpoint scoping | Ranked typed endpoints |
| `traceforge.load_plan` / `k6` | Bounded plan, script rendering, validation, execution | Script, summary, raw k6 log |
| `traceforge.signoz` | Runtime discovery and exact-window evidence retrieval | Sanitized MCP invocations and evidence |
| `traceforge.regression` | Numeric deltas, slopes, deterministic classification | Regression assessment |
| `traceforge.patching` / `worktree` | Reversion proposal, audit, isolated proof | Diff, audit, test/load proof |
| `traceforge.ledger` | Tamper-evident transition record | Per-run JSONL hash chain |
| `traceforge.release_proof` | Read-only projection of a run into a presentation contract | None |
| `apps/web` | API-backed live UI with partial/unavailable states | None |

SQLite stores current run state and transition idempotency records. Large raw outputs remain as
separate files under `.traceforge/runs/<run-id>/`; the database stores paths and typed summaries.

## Release-proof projection

`traceforge.release_proof` derives the presentation contract that the Release Proof page consumes. It
adds no new measurements. It reads the persisted run, intersects each retrieved span and log timestamp
with the exact phase window so evidence is attributed to the phase that produced it, and attaches
per-metric caveats where a raw delta would mislead — a latency improvement that accompanies a high
failure rate, or a throughput drop that the latency change alone predicts. Interpretation notes are
generated from the same persisted values, so the UI never computes a number the backend has not
recorded.

## Self-observability

The orchestrator exports its own workflow to the same SigNoz instance under service
`traceforge-orchestrator`. Each stage emits a span named after the stage, each SigNoz MCP tool
invocation emits a `signoz.mcp.call` span carrying `traceforge.mcp.tool` and success state, and all of
them carry `traceforge.run.id`, so one run's orchestration is isolatable. Target telemetry stays on
its own service name, which keeps the agent's spans from polluting the evidence it queries.

## Verdict invariants

`SHIP` requires every one of the following:

1. correlated baseline, candidate, and (when applicable) patched telemetry retrieved from SigNoz;
2. a sufficient deterministic assessment;
3. target tests passing in the managed patch worktree;
4. the exact same validated k6 script digest;
5. no patched threshold failure;
6. a verified improvement rather than merely a successful process exit; and
7. a valid terminal ledger chain.

If evidence is incomplete, TraceForge chooses `NEEDS_REVIEW`. A demonstrated regression or failed
proof chooses `BLOCK`. Infrastructure exceptions choose `FAILED` and retain their artifacts.
