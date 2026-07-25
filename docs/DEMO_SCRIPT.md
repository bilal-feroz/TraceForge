# Demo script

Two scripts live here. The **judged video** is 2.5–3 minutes and uses a pre-recorded run. The
**extended walkthrough** is 6–8 minutes for a live session where you can afford to wait for k6.

A `demo`-profile run takes roughly three minutes of wall clock for three 58-second phases plus
sandbox work, so do not try to run it live inside a three-minute video. Record the run first, then
narrate the persisted Release Proof view.

## Before either script

```bash
cp .env.example .env
uv sync --all-extras
pnpm install --frozen-lockfile
uv run python scripts/bootstrap_demo_repo.py
uv run traceforge doctor
```

Configure OTLP ingestion and SigNoz MCP as described in [SIGNOZ_SETUP.md](SIGNOZ_SETUP.md). The
doctor must show both paths available before you claim an evidence-backed result.

Terminal one:

```bash
uv run uvicorn traceforge.api:app --host 127.0.0.1 --port 8787
```

Terminal two:

```bash
pnpm --filter web build && pnpm --filter web start
```

Open `http://127.0.0.1:3000`. Import `infra/signoz/traceforge-release-proof.dashboard.json` into
SigNoz and set `run_id` to the run you recorded, so you can cut to it without typing a query.

## Judged video: 2.5–3 minutes

Timings are targets, not a straitjacket. Keep the failure-rate reveal before the 60-second mark.

**0:00–0:15 — the premise.** "A change can pass every unit test and still fail under real
concurrency. Nothing in a green CI run tells you that."

**0:15–0:30 — the change.** Show the candidate diff on `POST /api/visits`. It looks harmless: the
handler does a little work while holding a write transaction. No syntax error, no failing test.

**0:30–0:40 — start TraceForge.** `uv run traceforge demo lock --profile demo`. Say what it is about
to do: same bounded k6 experiment on both revisions, from detached worktrees at exact SHAs.

**0:40–0:50 — baseline.** Show the baseline phase in the Control Room: 5,524 requests, 0.09% failures,
P95 601.93 ms. This is the reference.

**0:50–1:05 — candidate, and the trap.** Show the candidate numbers: P95 *drops* to 340.19 ms and
throughput *rises* to 111.99 req/s. Pause on that. "A latency dashboard would call this an
improvement."

**1:05–1:20 — the real signal.** Reveal the failure rate: **94.40%**. "The tail got faster because
the requests stopped doing the work. They failed fast with `database is locked`." Show TraceForge's
own caveat text on the latency rows and the `ERROR_RATE_REGRESSION` classification.

**1:20–1:40 — server-side truth.** Cut to SigNoz: the candidate trace with the SQLite write span
holding the transaction, then the correlated logs filtered to that run and phase. "TraceForge did not
infer this from the diff. It queried the server through the SigNoz MCP server, correlated on
`traceforge.run.id`, and read it."

**1:40–1:55 — diagnosis and patch.** Show the evidence-backed root cause, then the generated diff.
Emphasize that it is minimal and reversible.

**1:55–2:10 — independent audit and sandbox.** Show the four audit checks passing (`scope`,
`applies_cleanly`, `signoz_grounding`, `reversible`), and that the patch is applied in a third
worktree, never in the source checkout.

**2:10–2:30 — proof, not hope.** The identical k6 script reruns on the patched revision: 0.16%
failures at baseline-like latency, with real patched-phase SigNoz evidence. Then the `SHIP` verdict.

**2:30–2:45 — the receipts.** `uv run traceforge ledger verify <run-id>` returning `"valid": true`
across 16 events, and one frame of the tamper check failing with `event hash mismatch` on a copy.

**2:45–2:55 — the agent watches itself.** Show service `traceforge-orchestrator` in SigNoz filtered
to that one run: 15 workflow stage spans plus one span per MCP tool call.

**Close.** "TraceForge does not guess from the diff. It runs the experiment, reads the server-side
truth from SigNoz, writes the fix, and proves it."

## Extended walkthrough: 6–8 minutes

### Opening

"TraceForge is a pre-production reliability agent. It does not ask a model whether a change looks
risky. It runs the same bounded experiment on both revisions, queries the server truth from SigNoz,
and lets a fix ship only after isolated proof."

Point out the SigNoz status indicator and the previous-runs list in the Control Room.

### Scenario 1: SQLite lock regression

```bash
uv run traceforge demo lock --profile demo
```

Narrate while it runs:

1. Git inspection identifies the changed `/api/visits` handler, not every route in the file.
2. The typed plan becomes a validated k6 program with fixed budgets and correlation headers.
3. Baseline and candidate run from detached worktrees at exact SHAs, same script digest.
4. k6 shows client symptoms; SigNoz establishes database contention with correlated server spans and
   `database is locked` logs.
5. TraceForge proposes only a minimal reversion of the diagnosed file, audits it independently, and
   applies it in a third worktree.
6. Tests and the identical load script run again, and the patched SigNoz window is queried before any
   verdict is published.

Walk the Release Proof sections in order, then run `uv run traceforge ledger verify <run-id>`.

### Scenario 2: silent latency degradation

```bash
uv run traceforge demo latency --profile demo
```

`/api/events` keeps returning HTTP 200 while retained state grows and each request rescans it. In the
measured run, P95 went 103.91 ms → 2,376.92 ms with a **0.00% failure rate** and a window slope of
+320.99 ms. Make the point plainly: the classifier combines P95 delta, ordered-window slope, and
SigNoz spans, and it never equates "HTTP 200" with "healthy."

### Scenario 3: no-regression control

```bash
uv run traceforge demo control --profile demo
```

This change touches harmless health metadata. TraceForge still requires correlated evidence, measures
`NO_REGRESSION`, and generates no patch. Mention the honest part: an earlier control run tripped the
throughput gate, we traced it to the closed-loop k6 plan making throughput a function of latency, and
fixed the classifier rather than loosening the threshold. That story is in
[BENCHMARKS.md](BENCHMARKS.md).

### Honest fallback

If SigNoz is unreachable, keep the run on screen:

```text
SigNoz verification unavailable
Verdict: NEEDS_REVIEW
```

Show the real k6 measurements and the recorded unavailable reason, but do not present a diagnosis,
patch, or `SHIP` verdict. This is a safety property, not a demo mode.

## One-command helpers

PowerShell:

```powershell
.\scripts\demo.ps1 lock -Profile quick
```

macOS/Linux:

```bash
./scripts/demo.sh lock quick
```

Accepted scenarios are `lock`, `latency`, and `control`. Rehearse with `quick`; record with `demo`.
