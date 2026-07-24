# TraceForge — hackathon submission

## Tagline

Load-test the change. Find the regression in SigNoz. Write and verify the smallest fix.

## Problem

Tests can pass while a change introduces lock contention, rising tail latency, or throughput loss.
Load tools show symptoms, code review shows intent, and observability shows server behavior—but the
evidence is usually fragmented and remediation is rarely re-tested under the same experiment.

## Solution

TraceForge is an evidence-first pre-production reliability agent. It:

1. inspects a base/candidate Git change and scopes affected API endpoints;
2. compiles a typed, budgeted k6 plan;
3. runs real paired experiments from isolated worktrees;
4. retrieves the exact correlated traces, logs, metrics, services, operations, and attributes
   through SigNoz MCP;
5. classifies regressions with deterministic numeric rules;
6. proposes only a scoped, reversible patch;
7. audits and applies it in a third worktree; and
8. reruns tests, identical load, and SigNoz verification before `SHIP`, `BLOCK`, or
   `NEEDS_REVIEW`.

## Why SigNoz is central

SigNoz is a hard workflow dependency rather than a screenshot destination. Without correlated
server-side telemetry, TraceForge cannot reach `TELEMETRY_CONFIRMED`, cannot issue an
evidence-backed diagnosis, and cannot publish `SHIP`. It states `SigNoz verification unavailable`
and stops at `NEEDS_REVIEW`.

TraceForge also exports its own orchestration spans, making the reliability agent observable while
it investigates the target.

## Technical highlights

- Python 3.12, FastAPI, Pydantic, SQLite, Typer, OpenTelemetry, official MCP Python SDK
- k6 v2 real subprocess validation and machine-summary parsing
- Next.js App Router, React, TypeScript, Tailwind CSS
- legal-transition state machine with idempotent durable events
- SHA-256 hash-chained per-run audit ledger with tamper tests
- runtime MCP tool/schema discovery, redacted invocation audit, bounded retries and ingestion wait
- changed-hunk-aware endpoint extraction
- generated Git histories for lock, silent-latency, and control scenarios
- argument-array subprocesses, host/repository allowlists, load caps, worktree-scoped patches

## Demonstration

The primary scenario changes one SQLite handler so simulated work occurs while an immediate write
transaction is held. Under concurrency the candidate produces lock errors and worse tails. SigNoz
connects those client symptoms to DB spans and logs. TraceForge derives a minimal reversion, applies
it outside the source checkout, runs tests and the same k6 script, then queries the new telemetry
window.

The silent-latency scenario demonstrates successful HTTP responses with a growing latency slope.
The control scenario demonstrates restraint: sufficient evidence with no material regression yields
no patch.

## Evidence and reproducibility

- Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Setup: [`SIGNOZ_SETUP.md`](SIGNOZ_SETUP.md)
- Demo: [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md)
- Threat model: [`THREAT_MODEL.md`](THREAT_MODEL.md)
- Measured and planned benchmarks: [`BENCHMARKS.md`](BENCHMARKS.md)
- Environment lockfiles: `uv.lock` and `pnpm-lock.yaml`
- Container entry point: root `docker-compose.yml`

The checked-in benchmark record is explicitly labeled as a single local measurement with SigNoz
unavailable. No telemetry, accuracy number, or screenshot is fabricated.

## Originality

TraceForge has an original forge/flight-recorder product identity, typed evidence contract,
state-machine workflow, hash ledger, graphite/ember/cyan interface, demo histories, and
documentation. It does not reuse another agent project's source, naming, layout, terminal
experience, copy, or visuals.

## AI assistance disclosure

OpenAI Codex assisted with architecture, implementation, tests, and documentation. Deterministic
code—not a model—owns regression rules, state transitions, patch scope, ledger verification, and
verdict gates. The repository includes executable tests and raw measurements so reviewers can
audit the result.
