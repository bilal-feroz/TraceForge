# Benchmarks

## Reporting policy

Results are labeled **measured**, **planned**, or **unavailable**. A single local run is a smoke
measurement, not a statistical performance claim. Raw machine-readable records live under
`benchmarks/raw`; per-run k6 summaries and logs remain under the ignored `.traceforge` directory.

Every number below comes from one execution of the named command on one machine. None of them is a
benchmark in the statistical sense, and none should be quoted as a product performance figure.

## Platform for the 2026-07-25 measurements

Windows amd64, Python 3.12, uv 0.11.32, k6 v2.1.0, Node v22.16.0, loopback FastAPI/SQLite target,
SigNoz Cloud with live OTLP ingestion and MCP evidence retrieval. Profile `demo`: three ordered
phases of roughly 58.6 seconds each, identical k6 script digest across phases within a run.

## Measured: SQLite write-lock regression (single run)

Command: `uv run traceforge demo lock --profile demo`
Run ID: `a2a7d676-038f-4e3c-8fd5-10cc3b8246b7`
Classification: `ERROR_RATE_REGRESSION` · Verification: `VERIFIED_IMPROVEMENT` · Verdict: `SHIP`

| Measurement | Baseline | Candidate | Patched |
| --- | ---: | ---: | ---: |
| Requests | 5,042 | 6,740 | 5,486 |
| Throughput | 86.87 req/s | 116.06 req/s | 94.52 req/s |
| P50 latency | 48.89 ms | 110.36 ms | 47.49 ms |
| P95 latency | 713.40 ms | 364.11 ms | 607.55 ms |
| P99 latency | 2,758.95 ms | 444.80 ms | 2,453.45 ms |
| HTTP failure rate | 0.18% | 94.55% | 0.07% |
| Checks failed | 93 | 6,373 | 88 |

Read the failure rate first. The candidate's P95 and P99 improved and its throughput rose only
because 94.55% of requests failed fast with `database is locked` instead of completing the write.
TraceForge classifies on the error rate for exactly this reason, and the release-proof view labels
the candidate latency columns as not-an-improvement. The patched phase restores a 0.07% failure rate
at baseline-like latency, which is the comparison that supports the `SHIP` verdict.

SigNoz evidence: available for all three phases, service `traceforge-demo-target`, ten correlated
trace IDs per phase, correlated `database is locked` logs on the candidate phase, and ten distinct
MCP tools used per phase.

Patch audit for this run: `traceforge-deterministic-auditor` passed all four independent checks —
`scope`, `applies_cleanly`, `signoz_grounding`, and `reversible`.

### Second lock run (classification reproducibility)

Command: same. Run ID `50ef7693-1eb8-4050-8ae8-1de5c76f83b2`, 45 minutes later on the same machine.

| Measurement | Baseline | Candidate | Patched |
| --- | ---: | ---: | ---: |
| Requests | 5,524 | 6,499 | 5,637 |
| Throughput | 95.20 req/s | 111.99 req/s | 97.16 req/s |
| P95 latency | 601.93 ms | 340.19 ms | 605.61 ms |
| HTTP failure rate | 0.09% | 94.40% | 0.16% |

Two runs is not a distribution, but the classification, verification status, verdict, and the shape
of the failure-rate signal reproduced exactly (`ERROR_RATE_REGRESSION` → `VERIFIED_IMPROVEMENT` →
`SHIP`), while absolute latencies moved by tens of milliseconds between runs. Treat the absolute
numbers as machine-specific and the classification as the reproducible result.

## Measured: silent latency degradation (single run)

Command: `uv run traceforge demo latency --profile demo`
Run ID: `45674c9c-bc70-4e64-9664-8bb9ae0ad1bf`
Classification: `SILENT_DEGRADATION` · Verification: `VERIFIED_IMPROVEMENT` · Verdict: `SHIP`

| Measurement | Baseline | Candidate | Patched |
| --- | ---: | ---: | ---: |
| Requests | 23,140 | 1,185 | 20,457 |
| Throughput | 398.91 req/s | 20.43 req/s | 352.67 req/s |
| P50 latency | 27.23 ms | 404.40 ms | 36.67 ms |
| P95 latency | 103.91 ms | 2,376.92 ms | 92.85 ms |
| P99 latency | 134.27 ms | 2,574.83 ms | 123.93 ms |
| HTTP failure rate | 0.00% | 0.00% | 0.00% |
| Ordered P95 windows | 18.8 → 46.9 ms | 218.8 → 2,575.3 → 1,206.6 ms | 23.5 → 41.8 ms |

Every candidate response was a successful HTTP 200. The detector fired on the ordered-window slope
of **+320.99 ms per window** combined with the P95 delta, which is the signal a pass/fail test suite
cannot produce. The patched phase returns the slope to baseline shape and beats the baseline P95.

## Measured: no-regression control (single run)

Command: `uv run traceforge demo control --profile demo`
Run ID: `a53f317c-a4c9-4843-8441-9cb3fa0f3da9`
Classification: `NO_REGRESSION` · Verification: `VERIFIED_NO_CHANGE` · Verdict: `SHIP`, no patch

| Measurement | Baseline | Candidate |
| --- | ---: | ---: |
| Requests | 28,052 | 27,253 |
| Throughput | 483.60 req/s | 469.84 req/s |
| P50 latency | 25.51 ms | 26.59 ms |
| P95 latency | 72.63 ms | 76.14 ms |
| P99 latency | 116.06 ms | 116.94 ms |
| HTTP failure rate | 0.00% | 0.00% |

No patch was generated, no root cause was invented, and SigNoz evidence was still required and
retrieved. The run stops after the candidate phase because there is nothing to remediate.

## Measured: closed-loop throughput false positive, found and fixed

An earlier control run on the same day was classified `THROUGHPUT_REGRESSION` even though the change
was harmless. The cause was real and worth recording: the k6 plan is a closed-loop ramping-VUs
schedule, so the client holds roughly constant concurrency and the completion rate is a function of
latency. A latency wobble of 28.18 ms → 45.14 ms mechanically produced 441.30 → 280.30 req/s, and
the throughput gate read that restatement as an independent regression.

The fix is in the classifier, not in the thresholds. `assess_regression` now computes the throughput
that latency alone predicts (`baseline_rate × baseline_p50 / candidate_p50`) and the implied
in-flight concurrency from Little's law. A throughput drop within 20% of the latency-predicted rate
is reported as explained rather than counted as a regression, and the reason is stated in the run's
deterministic reasons. Both directions are covered by unit tests in `tests/unit/test_regression.py`,
including a test built from the measured numbers above and a test proving an unexplained drop still
classifies as `THROUGHPUT_REGRESSION`.

## Measured: ledger integrity and tamper detection

| Run | Events | Terminal state | `ledger verify` |
| --- | ---: | --- | --- |
| `a2a7d676` lock | 16 | `PASSED` | valid |
| `50ef7693` lock | 16 | `PASSED` | valid |
| `45674c9c` latency | 16 | `PASSED` | valid |
| `a53f317c` control | 13 | `PASSED` | valid |
| `b0e0e11b` earlier lock | 16 | `PASSED` | valid |

Tamper check on a temporary copy of the lock ledger, with the original never opened for writing:
changing a single character of the `output_digest` on event 9 (`telemetry.correlate`) produced
`valid: false` with `event 9: event hash mismatch`, and re-verifying the untouched original still
returned `valid: true`.

## Measured: self-observability span inventory

Aggregated through MCP with `signoz_aggregate_traces` grouped by span name on service
`traceforge-orchestrator`, filtered to `traceforge.run.id = '50ef7693-1eb8-4050-8ae8-1de5c76f83b2'`,
a single lock run emitted 16 distinct span names:

| Span | Count |
| --- | ---: |
| `signoz.mcp.call` | 33 |
| `k6.execute` | 3 |
| `repository.inspect`, `change.read`, `endpoint.extract`, `load.plan.generate` | 1 each |
| `k6.script.render`, `k6.script.validate`, `signoz.preflight`, `telemetry.correlate` | 1 each |
| `regression.classify`, `diagnosis.generate`, `patch.generate`, `patch.audit` | 1 each |
| `verification.execute`, `verdict.publish` | 1 each |

`k6.execute` appears three times because the same script runs for baseline, candidate, and patched.
The 33 `signoz.mcp.call` spans are the individual MCP tool invocations, each carrying
`traceforge.mcp.tool` and `traceforge.run.id`, which is what makes the MCP-call and MCP-failure
panels on the SigNoz dashboard queryable.

## Measured: earlier local smoke run without SigNoz

Date: 2026-07-24 · Profile `quick` · Run ID `bd396850-960e-405c-ab92-3bb9ceaf5c7d`

| Measurement | Baseline | Candidate | Observation |
| --- | ---: | ---: | --- |
| Requests | 1,329 | 1,288 | Measured |
| Throughput | 83.05 req/s | 80.14 req/s | −3.50% |
| P95 latency | 76.34 ms | 126.08 ms | +49.74 ms / +65.16% |
| P99 latency | 114.40 ms | 153.09 ms | +38.69 ms / +33.82% |
| HTTP failure rate | 0.00% | 91.07% | Candidate threshold failed |
| Checks failed | 0 | 1,173 | Candidate threshold failed |
| Script digest equal | yes | yes | `2a22c659…a89e0` |

SigNoz status for that run: **unavailable**, because no account credentials were present. The
terminal state was `NEEDS_REVIEW`; no classification, diagnosis, patch, or `SHIP` claim was made. The
raw record is [`benchmarks/raw/2026-07-24-lock-quick.json`](../benchmarks/raw/2026-07-24-lock-quick.json).

## Planned validation matrix

| Scenario | Repetitions | Primary expected signal | Status |
| --- | ---: | --- | --- |
| SQLite write-lock regression | 10 paired runs | Errors + DB span/log concentration | Planned; 1 run measured |
| Silent unbounded-state latency | 10 paired runs | P95 delta + positive window slope | Planned; 1 run measured |
| Harmless health metadata control | 20 paired runs | `NO_REGRESSION`, no patch | Planned; 1 run measured |
| Ledger byte tamper | Every test run | Verification fails | Measured and automated |
| Missing telemetry | Every no-credential run | `NEEDS_REVIEW`, never `SHIP` | Measured and automated |

For the repeated suite, publish medians and median absolute deviations, classification counts,
false-positive/false-negative counts, hardware, dependency versions, and every raw run record.

## Unavailable

- Multi-machine or CI-hosted timings: not collected.
- Statistical confidence intervals: not computable from one run per scenario.
- Concurrency beyond the `demo` profile caps: not exercised.

## Reproduction

```bash
uv run python scripts/bootstrap_demo_repo.py
uv run traceforge demo lock --profile demo
uv run traceforge demo latency --profile demo
uv run traceforge demo control --profile demo
uv run traceforge ledger verify <run-id> --json
```

Local scheduling, filesystem, antivirus, thermal, and OneDrive activity can materially affect
loopback timings. Compare paired phases within a run and do not generalize these values to another
machine.
