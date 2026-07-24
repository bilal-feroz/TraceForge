# TraceForge implementation plan

Updated: 2026-07-24

## Repository inspection

The repository was empty except for its Git metadata. There was no user code to preserve and the
`main` branch had no commits. The initial machine has Git, Node 22, pnpm 11, Docker CLI, and Python
3.11. It does not initially have Python 3.12, `uv`, or k6. TraceForge targets Python 3.12 and its
doctor command reports these gaps without claiming the integration is usable.

## Product boundary

The first complete slice is local-only and evidence-first:

1. Validate a Git repository and revisions.
2. inspect the diff and discover FastAPI/OpenAPI endpoints;
3. build and validate a typed deterministic load plan;
4. render a constrained k6 program;
5. execute base and candidate experiments when k6 and target lifecycle configuration are present;
6. persist raw artifacts separately from typed summaries;
7. query SigNoz through a runtime-discovered MCP tool surface;
8. refuse `SHIP` whenever SigNoz evidence or patch verification is missing;
9. append every transition to a tamper-evident ledger; and
10. expose the same run through the CLI, versioned API, SSE, and web UI.

## Major assumptions

- TraceForge controls only local Git worktrees. Arbitrary public API shell commands are forbidden.
- Target process commands use a structured allowlist and are accepted only in explicitly enabled
  trusted-local mode. Demo commands use the bundled target lifecycle adapter.
- Network targets default to loopback. Non-local targets require an explicit allowlist entry.
- Repository text, MCP content, and generated patches are untrusted inputs.
- An LLM is optional. Deterministic endpoint scoping, plan rendering, regression classification,
  state transitions, ledger checks, and verification gates do not depend on a model.
- The official MCP Python SDK stable v1 API is pinned below v2 because v2 is not yet stable on the
  inspection date. The client adapter performs runtime tool discovery and contains the version
  boundary.
- k6 v2's machine-readable summary is preferred; the parser also accepts the established legacy
  `handleSummary` shape. Missing k6 is an honest hard failure for real experiments.
- No private SigNoz account is assumed. Unit/integration tests use a controlled MCP server only;
  a real account test is opt-in.

## Phases and exit criteria

### Phase 1 — executable engine

- Typed contracts, SQLite migrations, state machine, hash ledger.
- Git inspection, endpoint extraction, plan validation/rendering, k6 lifecycle and parsing.
- FastAPI API, SSE event stream, and professional CLI.
- Demo target and deterministic demo repository bootstrap.
- Unit and local integration coverage.

Exit: the local no-SigNoz path produces a real run and an honest `NEEDS_REVIEW`, never fabricated
evidence.

### Phase 2 — observability as a dependency

- OTLP instrumentation for target and orchestrator.
- Streamable HTTP SigNoz MCP client with discovery, schema checks, retries, sanitization, invocation
  audit, and bounded ingestion polling.
- Exact run-window correlation for traces, logs, metrics, operations, and services.

Exit: only retrieved evidence can advance `TELEMETRY_CONFIRMED`.

### Phase 3 — governed remediation

- Evidence-first diagnosis, scoped unified diff proposal, independent deterministic audit.
- Temporary worktree application, test/static checks, same-script rerun, telemetry comparison.
- Hard `SHIP` gate on successful tests, thresholds, improvement, and SigNoz retrieval.

### Phase 4 — reproducible demonstrations

- SQLite lock, silent-latency, and no-regression Git histories.
- Cross-platform bootstrap/demo/doctor scripts.
- Raw, reproducible benchmark output with unavailable values marked as such.

### Phase 5 — live web experience

- Original graphite/ember/cyan Control Room with live timeline.
- Evidence, diagnosis, patch, and proof views backed only by API data.
- Complete loading, empty, partial, error, and unavailable states.

### Phase 6 — quality and handoff

- Ruff, mypy, pytest, frontend typecheck/lint/build.
- Smoke execution and ledger tamper test.
- Architecture, setup, threat model, benchmarks, demo script, and submission documentation.

## Security decisions

- All subprocesses use argument arrays and timeouts; no `shell=True`.
- Repositories must resolve to a configured root and a real Git top level.
- URLs are parsed and checked against the target allowlist before load generation.
- Load plans have hard VU, duration, stage, body, and output limits.
- MCP requests are generated from discovered JSON schemas; credentials and authorization-like
  fields are redacted from records.
- Patches are parsed for file scope and secret patterns before touching a worktree.
- Worktree removal is explicit and scoped to paths created under a run artifact directory.

