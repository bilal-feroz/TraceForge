# TraceForge — hackathon submission

## Title

TraceForge — an autonomous pre-production reliability agent

## Tagline

Load-test the change. Find the regression in SigNoz. Write and verify the smallest fix.

## Short description

TraceForge runs the same bounded k6 experiment on a base and candidate revision, reads the
server-side truth from SigNoz through the official MCP server, classifies the regression with
deterministic rules, writes a minimal patch, audits it, reruns the identical experiment in a sandbox,
and publishes a `SHIP`, `BLOCK`, or `NEEDS_REVIEW` verdict backed by a hash-chained ledger.

## Long description

Pre-production checks tell a reviewer that tests passed. They do not tell the reviewer how a change
behaves under concurrency or where server time is spent. TraceForge closes that gap by treating a code
change as an experiment rather than a diff to be judged.

Given a repository and two revisions, it scopes the affected API endpoints from the changed hunks,
compiles a typed and budgeted k6 plan, and runs paired experiments from detached worktrees at exact
SHAs with an identical script digest. Every generated request carries correlation headers that become
OpenTelemetry attributes, so the exact experiment window can be retrieved server-side afterwards.

It then queries SigNoz through the hosted MCP server for the traces, logs, metrics, services,
operations, and attribute values belonging to that window, correlates them with the client-side k6
results, and classifies the outcome numerically. If there is a regression, it produces an
evidence-backed root cause, proposes the smallest reversible patch, audits that patch independently,
applies it in a third worktree, reruns the identical load, and queries the patched telemetry window
before any verdict is allowed. Every state transition is appended to a per-run SHA-256 hash chain.

TraceForge also exports its own orchestration as OpenTelemetry spans, so the agent is observable while
it investigates the target.

## Problem

Tests can pass while a change introduces lock contention, rising tail latency, or throughput loss.
Load tools show symptoms, code review shows intent, and observability shows server behavior — but the
evidence is fragmented, and a proposed remediation is rarely re-tested under the same experiment.

Worse, the symptoms can invert the conclusion. Our primary scenario is a change where the candidate's
P95 and P99 *improve* and throughput *rises*, because 94.55% of requests fail fast instead of doing
the write. A latency panel would approve it.

## Solution

TraceForge is an evidence-first pre-production reliability agent. It:

1. inspects a base/candidate Git change and scopes affected API endpoints from changed hunks;
2. compiles a typed, budgeted k6 plan and validates the rendered script;
3. runs real paired experiments from isolated worktrees with an identical script digest;
4. retrieves the exact correlated traces, logs, metrics, services, operations, and attributes through
   SigNoz MCP;
5. classifies regressions with deterministic numeric rules, not model judgment;
6. proposes only a scoped, reversible patch;
7. audits and applies it in a third worktree; and
8. reruns tests, identical load, and SigNoz verification before `SHIP`, `BLOCK`, or `NEEDS_REVIEW`.

## How TraceForge works

The workflow is a legal-transition state machine with durable, idempotent events. The stages are
observable by name in SigNoz: `repository.inspect`, `change.read`, `endpoint.extract`,
`load.plan.generate`, `k6.script.render`, `k6.script.validate`, `k6.execute` (once per phase),
`signoz.preflight`, `telemetry.correlate`, `regression.classify`, `diagnosis.generate`,
`patch.generate`, `patch.audit`, `verification.execute`, `verdict.publish`, plus one
`signoz.mcp.call` span per MCP tool invocation.

Classification is deterministic. Error-rate, latency-delta, window-slope, and throughput gates run on
the parsed k6 summaries, cross-checked against server-side span concentration. Throughput is
interpreted against the closed-loop nature of the load plan: a drop that the latency change alone
predicts is reported as explained rather than counted as an independent regression.

## SigNoz usage

SigNoz is a hard workflow dependency, not a screenshot destination. Without correlated server-side
telemetry, TraceForge cannot reach `TELEMETRY_CONFIRMED`, cannot issue an evidence-backed diagnosis,
and cannot publish `SHIP`; it records `SigNoz verification unavailable` and stops at `NEEDS_REVIEW`.

Through the hosted SigNoz MCP server (v0.9.0, 41 tools discovered at runtime) each run used:
`signoz_list_services`, `signoz_get_service_top_operations`, `signoz_get_field_keys`,
`signoz_get_field_values`, `signoz_search_traces`, `signoz_aggregate_traces`, `signoz_search_logs`,
`signoz_aggregate_logs`, `signoz_list_metrics`, and `signoz_query_metrics`. Tools and their input
schemas are discovered at runtime; arguments are validated against the discovered schema before any
call.

TraceForge ships a native dashboard definition, **TraceForge — Release Proof**, with `run_id`,
`phase`, and `service_name` variables and sixteen trace- and log-derived panels — including
TraceForge's own stage durations, MCP tool calls, and MCP tool failures.

## Technical implementation

- Python 3.12, FastAPI, Pydantic, SQLite, Typer, OpenTelemetry, official MCP Python SDK
- k6 v2 real subprocess execution with machine-summary parsing and script-digest equality checks
- Next.js App Router, React, TypeScript, Tailwind CSS; SSE for live run state
- legal-transition state machine with idempotent durable events
- SHA-256 hash-chained per-run audit ledger with tamper tests
- runtime MCP tool/schema discovery, redacted invocation audit, bounded retries and ingestion wait
- changed-hunk-aware endpoint extraction
- generated Git histories for lock, silent-latency, and control scenarios
- argument-array subprocesses, host/repository allowlists, load caps, worktree-scoped patches

## Real demo results

All three scenarios were executed on 2026-07-25 against live SigNoz Cloud with real OTLP ingestion.
Full tables are in [`BENCHMARKS.md`](BENCHMARKS.md).

**Lock contention** — run `a2a7d676-038f-4e3c-8fd5-10cc3b8246b7`, `ERROR_RATE_REGRESSION` →
`VERIFIED_IMPROVEMENT` → `SHIP`:

| Measurement | Baseline | Candidate | Patched |
| --- | ---: | ---: | ---: |
| P95 latency | 713.40 ms | 364.11 ms | 607.55 ms |
| Throughput | 86.87 req/s | 116.06 req/s | 94.52 req/s |
| HTTP failure rate | 0.18% | 94.55% | 0.07% |

The candidate's better tail is an artifact of 94.55% fast failures with `database is locked`. A second
lock run, `50ef7693-1eb8-4050-8ae8-1de5c76f83b2`, reproduced the classification, verification status,
and verdict with a 94.40% candidate failure rate.

**Silent degradation** — run `45674c9c-bc70-4e64-9664-8bb9ae0ad1bf`, `SILENT_DEGRADATION` → `SHIP`:
a 0.00% failure rate throughout, P95 103.91 ms → 2,376.92 ms, ordered-window slope +320.99 ms per
window, patched P95 92.85 ms.

**Control** — run `a53f317c-a4c9-4843-8441-9cb3fa0f3da9`, `NO_REGRESSION` → `SHIP` with no patch
generated: P95 72.63 ms → 76.14 ms at 0.00% failures.

**Ledger** — all four run ledgers verify (16, 16, 13, 16 events, terminal state `PASSED`). Flipping a
single character of one event's `output_digest` on a temporary copy produced
`event 9: event hash mismatch` while the untouched original still verified.

**Self-observability** — one lock run is queryable on service `traceforge-orchestrator` as 16 distinct
span names: all 15 workflow stages plus 33 `signoz.mcp.call` spans, filterable by
`traceforge.run.id`.

## Challenges

- **MCP response envelopes.** Tool results arrive wrapped, and the first parser silently produced
  empty evidence. Fixing it required parsing structured content and text blocks, then enforcing exact
  run-ID correlation so a partially matching window can never be accepted.
- **A real false positive.** A harmless control change was classified `THROUGHPUT_REGRESSION`. The
  cause was legitimate: the k6 plan is closed-loop, so at roughly constant client concurrency the
  completion rate is a function of latency, and a latency wobble of 28.18 ms → 45.14 ms mechanically
  produced 441.30 → 280.30 req/s. We fixed the classifier — it now computes the latency-predicted rate
  and the implied in-flight concurrency from Little's law — instead of loosening a threshold.
- **Misleading metrics as a first-class UI problem.** The lock scenario proves that a faster P95 can
  be the regression. The comparison view attaches caveats to specific metrics rather than leaving a
  green arrow to be misread.
- **Windows console encoding.** Redirected output crashed on the report's arrow characters until the
  CLI forced UTF-8 on stdout and stderr.
- **Dashboard write permissions.** The MCP write tools exist, but a least-privilege service-account
  key is refused with `403: only editors/admins can access this resource`. The CLI reports that
  verbatim and points to manual import rather than claiming success.

## Accomplishments

- A full loop that ends in a verdict supported by server-side evidence, not inference from a diff.
- Deterministic classification that survives an inverted-signal scenario a latency dashboard fails.
- A false positive found by running the control case honestly, then fixed at the root with tests
  covering both directions.
- Tamper-evident run history with a demonstrated detection.
- The agent is observable in SigNoz at stage granularity, including its own MCP calls.

## Lessons learned

- Client-side load metrics are symptoms. Without server-side correlation, the two most interesting
  cases — fast failures and silent latency growth — are both misread.
- Closed-loop load generators couple throughput to latency. A throughput gate that ignores this
  invents regressions.
- Running the control scenario is not a formality. It is where the false positives live.
- Refusing to produce a verdict is a feature. `NEEDS_REVIEW` when telemetry is unavailable is worth
  more than a confident guess.

## Future work

- Repeated paired runs per scenario with medians, MADs, and false-positive/false-negative counts.
- Open-model load plans (arrival-rate scenarios) so throughput becomes an independent signal.
- Target lifecycle adapters for general repositories and richer request-body inference.
- CI integration that posts the release proof to a pull request.
- Publishing the SigNoz dashboard automatically when an editor-scoped key is available.

## AI tool disclosure

OpenAI Codex and Cursor assisted with architecture, implementation, tests, and documentation.
Deterministic code — not a language model — owns regression calculations, legal state transitions,
patch scope checks, ledger integrity, and verdict gates. All generated work is reviewed through
executable tests, and every number in this document comes from a recorded run.

## Originality

TraceForge has an original product identity, typed evidence contract, state-machine workflow, hash
ledger, graphite/ember/cyan interface, demo histories, and documentation. It does not reuse another
agent project's source, naming, layout, terminal experience, copy, or visuals.

## Evidence and reproducibility

- Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Setup: [`SIGNOZ_SETUP.md`](SIGNOZ_SETUP.md)
- Demo: [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md)
- Screenshots: [`SCREENSHOTS.md`](SCREENSHOTS.md)
- Threat model: [`THREAT_MODEL.md`](THREAT_MODEL.md)
- Measured and planned benchmarks: [`BENCHMARKS.md`](BENCHMARKS.md)
- Dashboard definition: `infra/signoz/traceforge-release-proof.dashboard.json`
- Environment lockfiles: `uv.lock` and `pnpm-lock.yaml`
- Container entry point: root `docker-compose.yml`

## Links

- Repository: `<REPOSITORY_URL_PLACEHOLDER>`
- Demo video: `<DEMO_VIDEO_URL_PLACEHOLDER>`
- Live deployment: not applicable; TraceForge runs locally against your own SigNoz account.
