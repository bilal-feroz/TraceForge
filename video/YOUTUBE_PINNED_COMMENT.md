Thanks for watching.

Repo: https://github.com/bilal-feroz/TraceForge

Key numbers from the video (real runs, not synthetic):

- Lock run `50ef7693…`: k6 candidate failure rate 94.40%; SigNoz 3,158 / 3,522 error spans; 154 → 0 correlated lock-error logs; SHIP after sandbox proof
- Latency run `45674c9c…`: 0.00% failures while P95 went 103.91 → 2,376.92 ms; patched to 92.85 ms
- Control run `a53f317c…`: NO_REGRESSION, no unnecessary patch

SigNoz is the server-side source of truth. TraceForge will not publish a telemetry-dependent SHIP verdict without correlated evidence.

Questions about the MCP integration, the closed-loop throughput classifier, or the ledger welcome below.
