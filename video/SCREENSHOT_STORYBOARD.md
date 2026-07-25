# SigNoz screenshot storyboard

Fifteen real captures of the **TraceForge — Release Proof** dashboard, all from run
`50ef7693-1eb8-4050-8ae8-1de5c76f83b2` (the `demo lock` scenario) against service
`traceforge-demo-target`. They live in `video/assets/screenshots/`, copied byte-for-byte from the
originals; `manifest.json` records a SHA-256 for each one. Nothing was cropped, retouched, or
recompressed.

The uploads arrived baseline → patched → candidate. The story runs
**baseline → candidate regression → SigNoz evidence → patched recovery → self-observability**, so
the patched frames are held back until section D.

## What the numbers on screen actually are

The value tiles count **server-side spans inside the phase window**, which is not the same
population as k6's client-side request count. Both are true; they measure different things, and the
captions below only ever quote what is legible in the frame.

| | On the dashboard | k6 client-side, same run |
| --- | --- | --- |
| Baseline | 5,522 spans · 3 error spans · P95 600.85 ms | 5,524 requests · 0.09% failures · P95 601.93 ms |
| Candidate | 3,522 spans · 3,158 error spans · P95 281.15 ms | 6,499 requests · 94.40% failures · P95 340.19 ms |
| Patched | 5,633 spans · 5 error spans · P95 605.2 ms | 5,637 requests · 0.16% failures · P95 605.61 ms |

Two things to never say over these images: that the tile is the k6 request count, and that the
candidate is "94.4% errors". From these frames the candidate is 3,158 error spans out of 3,522,
which is 89.7% server-side. The 94.40% belongs to the TraceForge UI frames, not to these.

## A. Baseline — the healthy reference

**Frame A1 · `baseline-01-overview-kpis.png`** *(essential)*
Hold on the four value tiles with the `$phase = baseline` selector visible above them.

> Caption: **Baseline — 5,522 server-side spans, 3 error spans, P95 600.85 ms**
> Narration: "This is the base revision under real load, seen from the server side. Three error
> spans out of five and a half thousand. That is our reference."

Optional B-roll: `baseline-02-latency-and-status.png` for the green 201 donut (5,519 of 5,522), and
`baseline-03-lock-logs-slow-operations-traces.png` for the ~36 ms correlated spans.

## B. Candidate — the regression under real load

**Frame B1 · `candidate-01-overview-kpis.png`** *(essential)*
Cut on the identical framing as A1 so only the numbers move.

> Caption: **Candidate — 3,158 error spans, 3,158 lock-error logs, P95 281 ms**
> Narration: "Same load, same dashboard, one variable changed. The P95 actually *improved*, to 281
> milliseconds. That is the trap — three thousand one hundred and fifty-eight of these spans are
> errors."

**Frame B2 · `candidate-02-error-rate-and-status.png`** *(essential — the single strongest frame)*
Push into the donut on the right.

> Caption: **3,158 responses returned HTTP 500. 364 succeeded.**
> Narration: "The donut flips. The latency looked better because the failures returned faster than
> the work did."

## C. SigNoz evidence — errors, logs, traces, the lock

**Frame C1 · `candidate-03-lock-logs-slow-operations-traces.png`** *(essential)*
Open on the lock-error-logs panel, then pan right to the correlated traces.

> Caption: **The lock errors are in the logs, correlated to this run**
> Narration: "None of this is inferred from the diff. These are log records and spans carrying the
> run ID, counted inside the candidate window, retrieved through the SigNoz MCP server."

Known gap: the literal string `database is locked` is not legible anywhere in the set. The panel
*title* says it and the counter says 3,158, but the log body and `exception.message` cells are empty
in the visible rows. If the edit needs the words on screen, recapture that panel (see the recapture
list) or cut to the TraceForge Release Proof page, which renders the message text.

## D. Patched — recovery confirmed

**Frame D1 · `patched-01-overview-kpis.png`** *(essential)*
Same framing again. Three identical compositions, three different stories, is the whole argument.

> Caption: **Patched — 5,633 spans, 5 error spans, P95 605.2 ms**
> Narration: "After the patch, on the identical load script: five error spans instead of three
> thousand, at baseline latency. That is the comparison that earns a ship verdict."

Optional split screen: `candidate-02` beside `patched-02-latency-and-status.png` — the inverted
donut against the green one (5,628 of 5,633 at HTTP 201). Or `candidate-03` beside
`patched-03-lock-logs-slow-operations-traces.png`, where the same lock panel drops from a 2,500+
axis to a 0-10 axis.

## E. Self-observability — the agent watching itself

**Frame E1 · `candidate-04-correlated-evidence-and-stage-spans.png`** *(essential)*
Scroll or cut to the lower half: the stage-duration table and the MCP tool-call chart.

> Caption: **TraceForge's own workflow, in the same SigNoz instance**
> Narration: "While it investigated the target, TraceForge exported its own run: every workflow
> stage, and every SigNoz MCP call it made to reach the verdict."

Visible: `verification.execute`, `k6.execute` (6 spans — three phases, two runs of the panel's
window), `signoz.preflight`, `verdict.publish`, and six distinct MCP tools in the legend. These
panels are run-wide rather than phase-filtered, so they are identical in the baseline, candidate, and
patched captures — do not imply they changed between phases.

## Final cut — six frames, in order

| # | File | Section | Beat |
| --- | --- | --- | --- |
| 1 | `baseline-01-overview-kpis.png` | A | healthy reference |
| 2 | `candidate-01-overview-kpis.png` | B | the trap: better P95, 3,158 error spans |
| 3 | `candidate-02-error-rate-and-status.png` | B | 3,158 × HTTP 500 vs 364 × 201 |
| 4 | `candidate-03-lock-logs-slow-operations-traces.png` | C | lock errors and correlated traces |
| 5 | `patched-01-overview-kpis.png` | D | 5 error spans at baseline latency |
| 6 | `candidate-04-correlated-evidence-and-stage-spans.png` | E | stage spans and MCP calls |

Frames 1, 2, and 5 share identical framing on purpose: cut them without motion and let the numbers
do the work.

## Held back

| File | Priority | Why |
| --- | --- | --- |
| `baseline-02`, `baseline-03`, `baseline-04` | supporting | good B-roll, but the baseline only needs one beat |
| `patched-02`, `patched-03` | supporting | best use is a split-screen against their candidate twins |
| `patched-04` | supporting | its stage panels duplicate frame 6 exactly |
| `baseline-05`, `patched-05`, `candidate-05` | unused | near-duplicates of each other; two "No Data" panels each |

## Recapture before the final render

1. **Resolution (high).** Every file is 1024 px wide and has been through WhatsApp recompression.
   Full-frame on a 1080p timeline is a 1.9× upscale and a panel zoom is 3–4×, which will smear the
   text. Recapture at 1920 px or wider, saved as PNG without a messaging-app round trip.
2. **The lock message (high).** Widen or expand a candidate error row so `database is locked` is
   readable, rather than only its count.
3. **Candidate correlated traces (medium).** Every visible row shows status `Unset` at ~100 ms, so
   the failing spans never appear. Sort or filter by error status.
4. **Stage-duration table (medium).** Durations show as raw nanoseconds (`69049363160`) and the table
   mixes workflow stages with FastAPI routes like `GET /api/v1/runs`. Format as duration and filter
   to workflow spans.
5. **Time range (medium).** Every by-phase graph is a hairline spike on a 24-hour axis. Narrow the
   dashboard range to the run window so the shape means something.
6. **Failure panels (low).** Replace the "No Data" pair with a panel that renders an explicit zero,
   or leave them out.

Nothing above blocks a cut of the video with the six selected frames. Items 1 and 2 are the ones
worth redoing if there is time before recording.
