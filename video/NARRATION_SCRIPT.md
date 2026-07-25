# TraceForge demo narration

Target pace: ~150 words per minute. Neutral international English. Calm, technical, not salesy.

Total spoken length: approximately 2 minutes 40 seconds of narration across a ~2:50 picture cut.

## Scene 1 — Hook (0:00–0:09)

This change passes every unit test. But under real concurrent traffic, more than ninety-four percent of requests fail.

## Scene 2 — Problem (0:09–0:23)

Concurrency, latency, and dependency regressions often remain invisible until production. Reproducing realistic load and correlating the server-side evidence still takes too much manual work.

## Scene 3 — TraceForge (0:23–0:39)

TraceForge automates the full release-proof loop. It inspects the change, generates a deterministic k6 experiment, reads traces and logs through SigNoz, writes a minimal fix, and reruns the identical test to prove the result.

## Scene 4 — Baseline (0:39–0:52)

First, TraceForge establishes a healthy baseline from the unchanged revision.

## Scene 5 — Candidate regression (0:52–1:09)

The candidate appears faster at the tail, but that number is deceptive. Failed lock requests return quickly. The decisive signal is the failure rate: ninety-four point four percent at the client, with three thousand one hundred fifty-eight server-side error spans.

## Scene 6 — SigNoz evidence (1:09–1:31)

TraceForge queries the exact experiment window through SigNoz MCP. The status distribution inverts, lock errors spike, and the correlated traces point to POST slash API slash visits. The release-proof projection finds one hundred fifty-four correlated lock-error logs in the candidate phase and zero after the patch.

## Scene 7 — Root cause (1:31–1:44)

The root cause is specific and reviewable: the candidate holds an immediate SQLite write lock during simulated work while allowing only a ten-millisecond busy timeout.

## Scene 8 — Patch and audit (1:44–1:59)

TraceForge generates the smallest relevant patch. A separate audit verifies the telemetry grounding, patch scope, reversibility, tests, and safety before the change is applied.

## Scene 9 — Patched proof (1:59–2:15)

The patch runs only inside an isolated sandbox. TraceForge executes the identical experiment again. Failures fall from ninety-four point four percent to zero point one six percent, lock errors disappear, and the release is marked ship.

## Scene 10 — Silent latency (2:15–2:28)

It also catches failures that never produce an error. In the silent-degradation scenario, failure rate stays at zero while P95 climbs beyond two seconds. TraceForge detects the latency trend and verifies a patch back below the original baseline.

## Scene 11 — Control, trust, self-observability (2:28–2:39)

A harmless control change passes without an unnecessary patch. Every workflow stage and MCP call is observable in SigNoz, while the hash-chained ledger makes every transition replayable and tamper-evident.

## Scene 12 — Closing (2:39–2:50)

TraceForge does not guess from the diff. It runs the experiment, reads the server-side truth from SigNoz, writes the fix, and proves it.

## Pronunciation notes

- TraceForge — TRACE-forge
- SigNoz — SIG-nose
- OpenTelemetry — open-tuh-LEM-uh-tree
- k6 — kay-six
- P95 — pee-ninety-five
- SQLite — ess-cue-lite / sequel-lite
- MCP — em-see-pee
