# Threat model

## Assets

- source repositories and their uncommitted user changes;
- SigNoz ingestion and service-account credentials;
- target systems reachable from the runner;
- run evidence, diagnosis, proposed patches, and verdicts;
- integrity of the transition ledger and benchmark record.

## Trust assumptions

Repository content, Git metadata, endpoint declarations, MCP output, HTTP responses, logs, and any
future model output are untrusted. The local operator and the configured filesystem roots are
trusted. SigNoz transport security and account authorization remain the deployment owner's
responsibility.

## Controls

| Threat | Control | Residual risk |
| --- | --- | --- |
| Shell injection | Subprocesses receive argument arrays; `shell=True` is never used | A trusted executable may itself interpret unsafe arguments |
| Arbitrary repository execution | Disabled by default; CLI-only trusted-local switch; repo roots are allowlisted | Enabling local mode executes tests and target code with the runner's OS identity |
| SSRF / destructive load | Target host allowlist defaults to loopback; typed VU/duration caps | An allowlisted service can still mutate its own data |
| Path traversal / checkout damage | Paths resolve under allowlisted roots; experiments and patches use detached worktrees | Git hooks or platform-specific filesystem behavior require operator hardening |
| Patch scope expansion | Unified diff parser allows only files in the inspected change; `git apply --check`; independent audit | Minimal reversion can still alter intended behavior |
| Secret disclosure | `.env` ignored; credential-like fields redacted; raw authorization headers are not ledgered | Target logs can contain application secrets and should use a scrubber |
| Prompt / data injection | MCP and repository text are treated as data; deterministic code owns decisions | A future LLM-based explanation may still contain misleading prose |
| Evidence spoofing | Run ID, phase, scenario, SHA, exact windows, service name, and script digest are correlated | A malicious target can deliberately emit false attributes |
| Replay / duplicate transitions | Stable event IDs plus SQLite uniqueness | Database restoration can reintroduce an older valid state |
| Ledger tampering | SHA-256 hash chain, sequence checks, terminal-state validation | A writer able to replace the full ledger and database can forge both |
| Denial of service | Timeouts, output-byte limits, bounded retries, bounded ingestion polling, load budgets | High-cost but allowed targets can still consume local resources |
| Dependency compromise | Lockfiles and pinned major compatibility bounds; container tags should be pinned | This prototype does not generate or verify an SBOM/signature |

## High-risk operation: trusted local mode

`TRACEFORGE_TRUSTED_LOCAL_MODE=true` authorizes TraceForge to launch the explicitly provided target
command and run repository tests in managed worktrees. Use it only for repositories you would run
manually. It is never enabled by an API request.

For multi-user or CI deployment, run the orchestrator as an unprivileged identity inside a
short-lived VM/container with:

- a read-only source mirror;
- a dedicated writable run directory;
- no Docker socket;
- outbound network policy limited to the target, OTLP, and MCP endpoints;
- short-lived SigNoz credentials; and
- OS-level CPU, memory, process, and disk quotas.

## Data retention

`.traceforge` can contain raw target and k6 logs. It is intentionally not committed. Set filesystem
permissions and a retention job appropriate to the source and telemetry sensitivity. The web API
does not expose arbitrary artifact paths, but anyone with local filesystem access can read them.

## Explicit non-goals

- safely executing hostile repositories on a developer workstation;
- proving a target's telemetry is truthful;
- replacing production authorization, admission control, or change approval;
- automatically pushing branches, opening pull requests, or deploying a patch.
