# Demo script

Target length: 6–8 minutes. Run `quick` while rehearsing and `demo` for the judged presentation.

## Before the session

```bash
cp .env.example .env
uv sync --all-extras
pnpm install --frozen-lockfile
uv run python scripts/bootstrap_demo_repo.py
uv run traceforge doctor
```

Configure both OTLP ingestion and SigNoz MCP as described in
[SIGNOZ_SETUP.md](SIGNOZ_SETUP.md). The doctor must show both paths as available before claiming an
evidence-backed result.

In terminal one:

```bash
uv run uvicorn traceforge.api:app --host 127.0.0.1 --port 8787
```

In terminal two:

```bash
pnpm dev
```

Open `http://127.0.0.1:3000`.

## Opening

“TraceForge is a pre-production reliability agent. It does not ask an LLM whether a change looks
risky. It runs the same bounded experiment on both revisions, queries the server truth from SigNoz,
and permits a fix to ship only after isolated proof.”

Point out the SigNoz status indicator and the empty/previous-runs state in the Control Room.

## Scenario 1: SQLite lock regression

Run:

```bash
uv run traceforge demo lock --profile demo
```

In the UI, open the new run and narrate:

1. Git inspection identifies the changed `/api/visits` handler, not merely every route in the file.
2. The typed plan becomes a validated k6 program with fixed budgets and correlation headers.
3. Baseline and candidate run from detached worktrees at exact SHAs.
4. k6 shows client symptoms; SigNoz establishes database contention with correlated server spans and
   `database is locked` logs.
5. TraceForge creates only a minimal reversion of the diagnosed file, independently audits it, and
   applies it in a third worktree.
6. Tests and the identical load script run again. The patched SigNoz window is queried before a
   verdict is published.

Show the Evidence, Diagnosis, Patch, and Proof tabs. End by running:

```bash
uv run traceforge ledger verify <run-id>
```

## Scenario 2: silent latency degradation

```bash
uv run traceforge demo latency --profile demo
```

Explain that `/api/events` continues returning successful responses while retained state grows and
each request rescans it. The important signal is rising latency rather than 5xx errors. The
deterministic classifier combines P95 delta, ordered-window slope, and SigNoz spans; it does not
equate “HTTP 200” with “healthy.”

## Scenario 3: no-regression control

```bash
uv run traceforge demo control --profile demo
```

This change touches harmless health metadata. TraceForge still requires sufficient correlated
evidence, but it does not invent a patch. The control path proves the system can avoid false
positives.

## Honest fallback

If SigNoz is unreachable, keep the run:

```text
SigNoz verification unavailable
Verdict: NEEDS_REVIEW
```

Show the real k6 measurements and the recorded unavailable reason, but do not present a diagnosis,
patch, or `SHIP` verdict. This is an intentional safety property, not a demo mode.

## One-command helpers

PowerShell:

```powershell
.\scripts\demo.ps1 lock -Profile quick
```

macOS/Linux:

```bash
./scripts/demo.sh lock quick
```

Accepted scenarios are `lock`, `latency`, and `control`.
