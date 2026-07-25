# Screenshot checklist

Every image must come from a real run. Do not stage, retouch, or reconstruct a view that the code
does not produce. If a capture cannot be taken, leave the row unchecked rather than substituting a
mockup.

## Runs to use

| Purpose | Run ID | Scenario |
| --- | --- | --- |
| Primary regression story | `50ef7693-1eb8-4050-8ae8-1de5c76f83b2` | lock, fully instrumented |
| Alternate lock run | `a2a7d676-038f-4e3c-8fd5-10cc3b8246b7` | lock |
| Silent degradation | `45674c9c-bc70-4e64-9664-8bb9ae0ad1bf` | latency |
| Restraint / no false positive | `a53f317c-a4c9-4843-8441-9cb3fa0f3da9` | control |

## Before capturing

```bash
uv run uvicorn traceforge.api:app --host 127.0.0.1 --port 8787
pnpm --filter web build && pnpm --filter web start
```

Use the production frontend build, a 1600×1000 or larger viewport, and the browser's own zoom at
100%. Capture PNG. Save into `docs/images/` using the file names below.

## Redaction rules

Before saving any SigNoz capture, confirm the frame contains no API key, no ingestion key, no
`Authorization` header, and no query string carrying a token. Instance hostnames may appear only if
you accept publishing them; otherwise crop or blur the address bar. Never screenshot `.env`, a
terminal that has echoed a key, or a browser devtools network pane.

## TraceForge product UI

- [ ] `01-control-room.png` — Control Room run list with the four runs above visible, verdict badges
      readable.
- [ ] `02-release-proof-overview.png` — Release Proof top summary for the lock run: verdict, run ID,
      repository, base and candidate revision, endpoint, SigNoz evidence status, patch verification
      status, ledger status, created timestamp.
- [ ] `03-three-phase-comparison.png` — the baseline/candidate/patched table with the misleading-P95
      caveat text visible next to the latency rows. This is the single most important frame.
- [ ] `04-timeline.png` — experiment timeline with the three phase windows and their durations.
- [ ] `05-classification.png` — deterministic classification panel with gate inputs, including the
      implied client concurrency row.
- [ ] `06-diagnosis.png` — root-cause diagnosis with its SigNoz evidence references.
- [ ] `07-evidence-traces.png` — per-phase SigNoz evidence with candidate trace IDs listed.
- [ ] `08-evidence-logs.png` — correlated `database is locked` log lines for the candidate phase.
- [ ] `09-patch-diff.png` — generated unified diff.
- [ ] `10-patch-audit.png` — the four audit checks (`scope`, `applies_cleanly`, `signoz_grounding`,
      `reversible`) all passing.
- [ ] `11-verification-verdict.png` — sandbox verification result and the final `SHIP` verdict.
- [ ] `12-live-run.png` — a live run in progress: current stage, elapsed time, active phase, k6 status,
      MCP activity. Start `uv run traceforge demo lock --profile demo` and capture during the
      candidate phase.
- [ ] `13-latency-run.png` — Release Proof for the latency run showing the 0.00% failure rate beside
      the P95 climb and the positive window slope.
- [ ] `14-control-run.png` — Release Proof for the control run showing `NO_REGRESSION` and no patch
      section.

## SigNoz

- [ ] `20-signoz-release-proof-dashboard.png` — the native **TraceForge — Release Proof** dashboard
      with `run_id` set to the lock run. Import
      `infra/signoz/traceforge-release-proof.dashboard.json` first; publishing through MCP needs an
      editor or admin key.
- [ ] `21-signoz-candidate-trace.png` — one candidate trace from the lock run showing the SQLite write
      span holding the transaction.
- [ ] `22-signoz-candidate-logs.png` — the SigNoz logs view filtered to
      `traceforge.run.id = <lock run>` and `traceforge.phase = candidate`, showing
      `database is locked`.
- [ ] `23-signoz-patched-evidence.png` — the same views for `traceforge.phase = patched`, with the lock
      errors gone.
- [ ] `24-signoz-self-observability.png` — service `traceforge-orchestrator` filtered to one
      `traceforge.run.id`, showing the workflow stage spans and `signoz.mcp.call` spans together.

## Terminal

- [ ] `30-ledger-verify.png` — `uv run traceforge ledger verify <run-id>` returning
      `"valid": true` with the event count and terminal state.
- [ ] `31-ledger-tamper.png` — verification failing with `event N: event hash mismatch` on a temporary
      copy, alongside the original still verifying. Never tamper with a real run's ledger.
- [ ] `32-doctor.png` — `uv run traceforge doctor` showing OTLP and SigNoz MCP both available.

## Ordering for the submission

Lead with `03-three-phase-comparison.png`, then `22-signoz-candidate-logs.png`,
`10-patch-audit.png`, `11-verification-verdict.png`, and `24-signoz-self-observability.png`. Those
five frames carry the argument: the numbers lie, the server-side evidence explains why, the fix is
audited, the rerun proves it, and the agent is observable while doing it.
