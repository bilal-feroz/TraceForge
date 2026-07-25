# YouTube description

TraceForge is an autonomous pre-production reliability agent.

It load-tests a Git change with deterministic k6 experiments, reads the server-side truth through SigNoz MCP, diagnoses the regression with evidence, writes a minimal remediation patch, audits it independently, reruns the identical experiment in a sandbox, and publishes a SHIP / BLOCK / NEEDS_REVIEW verdict backed by a hash-chained audit ledger.

## Why SigNoz is essential

SigNoz is not a decorative dashboard in this design. Without correlated server-side traces and logs for the exact experiment window, TraceForge cannot issue an evidence-backed diagnosis or a telemetry-dependent SHIP verdict. Client-side k6 numbers alone are symptoms — SigNoz provides the server-side truth.

## Real demo results

Lock-contention run `50ef7693-1eb8-4050-8ae8-1de5c76f83b2`:

- Classification: ERROR_RATE_REGRESSION
- Candidate k6 failure rate: 94.40%
- SigNoz candidate window: 3,158 error spans out of 3,522 observed spans
- Release-proof lock-error logs: 154 → 0 after patch
- Patched k6 failure rate: 0.16%
- Verification: VERIFIED_IMPROVEMENT
- Verdict: SHIP

Silent-latency run `45674c9c-bc70-4e64-9664-8bb9ae0ad1bf`:

- Failure rate remained 0.00%
- P95: 103.91 ms → 2,376.92 ms
- Latency slope: +320.99 ms / window
- Patched P95: 92.85 ms
- Classification: SILENT_DEGRADATION
- Verdict: SHIP

No-regression control `a53f317c-a4c9-4843-8441-9cb3fa0f3da9`:

- Classification: NO_REGRESSION
- No patch generated
- Verdict: SHIP

Self-observability: 15 TraceForge workflow stages and 33 SigNoz MCP call spans appear on service `traceforge-orchestrator`.

Ledger: original chain verifies; a one-character tamper on a copy fails with an event hash mismatch.

## Stack

- OpenTelemetry
- SigNoz Cloud + official MCP server
- k6
- FastAPI / Next.js
- Hash-chained audit ledger

## Repository

https://github.com/bilal-feroz/TraceForge

## Hackathon context

Built for AI & Agent Observability — TraceForge uses SigNoz both as the decision source for code-change investigation and as the destination for its own workflow spans.

## AI assistance disclosure

OpenAI Codex and Cursor assisted with architecture, implementation, tests, documentation, and this video. Deterministic code — not a language model — owns regression calculations, legal state transitions, patch scope checks, ledger integrity, and verdict gates.

## Chapters

See YOUTUBE_CHAPTERS.txt
