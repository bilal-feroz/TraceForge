# Benchmarks

## Reporting policy

Results are labeled **measured**, **planned**, or **unavailable**. A single local run is a smoke
measurement, not a statistical performance claim. Raw machine-readable records live under
`benchmarks/raw`; per-run k6 summaries and logs remain under the ignored `.traceforge` directory.

## Measured local smoke run

Date: 2026-07-24  
Scenario: generated `demo-lock` versus `demo-baseline`  
Profile: `quick` (2-second warmup; 4s→2 VUs, 8s→8 VUs, 4s drain)  
Platform: Windows amd64, k6 v2.1.0, loopback FastAPI/SQLite target  
Run ID: `bd396850-960e-405c-ab92-3bb9ceaf5c7d`

| Measurement | Baseline | Candidate | Observation |
| --- | ---: | ---: | --- |
| Requests | 1,329 | 1,288 | Measured |
| Throughput | 83.05 req/s | 80.14 req/s | −3.50% |
| P95 latency | 76.34 ms | 126.08 ms | +49.74 ms / +65.16% |
| P99 latency | 114.40 ms | 153.09 ms | +38.69 ms / +33.82% |
| HTTP failure rate | 0.00% | 91.07% | Candidate threshold failed |
| Checks failed | 0 | 1,173 | Candidate threshold failed |
| Script digest equal | yes | yes | `2a22c659…a89e0` |

SigNoz status for this local measurement: **unavailable** because no account credentials were
present. The correct terminal state was `NEEDS_REVIEW`; no server-side classification, diagnosis,
patch, or `SHIP` claim was produced.

The checked-in raw record is
[`benchmarks/raw/2026-07-24-lock-quick.json`](../benchmarks/raw/2026-07-24-lock-quick.json).

## Planned validation matrix

| Scenario | Repetitions | Primary expected signal | Status |
| --- | ---: | --- | --- |
| SQLite write-lock regression | 10 paired runs | Errors + DB span/log concentration | Planned with real SigNoz |
| Silent unbounded-state latency | 10 paired runs | P95 delta + positive window slope | Planned with real SigNoz |
| Harmless health metadata control | 20 paired runs | `NO_REGRESSION`, no patch | Planned with real SigNoz |
| Ledger byte tamper | Every test run | Verification fails | Automated unit test |
| Missing telemetry | Every no-credential run | `NEEDS_REVIEW`, never `SHIP` | Measured and automated |

For the repeated suite, publish medians and median absolute deviations, classification counts,
false-positive/false-negative counts, hardware, dependency versions, and every raw run record.

## Reproduction

```bash
uv run python scripts/bootstrap_demo_repo.py
uv run traceforge demo lock --profile quick --json
uv run traceforge ledger verify <run-id> --json
```

Local scheduling, filesystem, antivirus, thermal, and OneDrive activity can materially affect
loopback timings. Compare paired phases within a run and do not generalize these values to another
machine.
