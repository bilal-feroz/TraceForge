# SigNoz setup

TraceForge uses two deliberately separate paths:

- OTLP ingestion sends target and orchestrator traces, logs, and metrics to SigNoz.
- SigNoz MCP is the read-only control plane used to discover tools and retrieve evidence.

An ingestion key is not an API key. Do not substitute one for the other.

## SigNoz Cloud

1. In SigNoz, open **Settings → Ingestion** and note the region and OTLP endpoint.
2. Create or copy an ingestion key.
3. Under **Settings → Service Accounts**, create a least-privilege API key that can read services,
   traces, logs, metrics, and field metadata.
4. Copy `.env.example` to `.env` and set:

```dotenv
SIGNOZ_REGION=<your-region>
SIGNOZ_INGESTION_KEY=<ingestion-key>
OTEL_EXPORTER_OTLP_ENDPOINT=https://ingest.<your-region>.signoz.cloud:443
OTEL_EXPORTER_OTLP_HEADERS=signoz-ingestion-key=<ingestion-key>
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

SIGNOZ_INSTANCE_URL=https://<your-instance>.signoz.cloud
SIGNOZ_API_KEY=<service-account-api-key>
SIGNOZ_MCP_URL=https://mcp.<your-region>.signoz.cloud/mcp
```

The MCP client uses Streamable HTTP with `SIGNOZ-API-KEY` and `X-SigNoz-URL` request headers. It
discovers tools and their input schemas at runtime; it does not assume that a globally installed
MCP configuration is available.

## Self-hosted SigNoz

Run the official SigNoz MCP server in HTTP mode and point it at your SigNoz instance:

```bash
docker run --rm -p 8000:8000 \
  -e TRANSPORT_MODE=http \
  -e MCP_SERVER_HOST=0.0.0.0 \
  -e MCP_SERVER_PORT=8000 \
  -e SIGNOZ_URL=http://host.docker.internal:3301 \
  -e SIGNOZ_API_KEY=<api-key> \
  signoz/signoz-mcp-server:<pinned-version>
```

Then configure TraceForge:

```dotenv
SIGNOZ_INSTANCE_URL=http://127.0.0.1:3301
SIGNOZ_API_KEY=<api-key>
SIGNOZ_MCP_URL=http://127.0.0.1:8000/mcp
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
OTEL_EXPORTER_OTLP_HEADERS=
```

Pin the MCP container version in durable environments. The example intentionally does not invent a
version for you; choose a reviewed release compatible with your SigNoz deployment.

## Correlation contract

Every generated request carries:

| HTTP header | OpenTelemetry attribute |
| --- | --- |
| `X-TraceForge-Run-Id` | `traceforge.run.id` |
| `X-TraceForge-Phase` | `traceforge.phase` |
| `X-TraceForge-Scenario` | `traceforge.scenario` |
| `X-TraceForge-Git-Sha` | `git.commit.sha` |

The target also exports `service.name`, `service.version`, and
`deployment.environment=preproduction`. TraceForge records exact UTC start/end timestamps around
each k6 process and adds a small bounded search margin for ingestion timing.

## Validation

Run:

```bash
uv run traceforge doctor
```

The SigNoz check must report that it connected and discovered the required live-data tools. A real
demo should then show both services:

- `traceforge-orchestrator`
- `traceforge-demo-target`

The investigation retrieves:

- service presence and top operations;
- trace/log attribute keys and the current run ID value;
- correlated trace rows and one complete trace;
- correlated log rows plus grouped log counts;
- grouped trace latency;
- metric catalog metadata and the custom request-duration time series.

The required metric name is `traceforge.demo.request.duration`.

TraceForge's own orchestration is queryable on `traceforge-orchestrator`. A completed lock run emits
`repository.inspect`, `change.read`, `endpoint.extract`, `load.plan.generate`, `k6.script.render`,
`k6.script.validate`, `k6.execute` (once per phase), `signoz.preflight`, `telemetry.correlate`,
`regression.classify`, `diagnosis.generate`, `patch.generate`, `patch.audit`, `verification.execute`,
`verdict.publish`, and one `signoz.mcp.call` span per MCP tool invocation. All of them carry
`traceforge.run.id`, so a single run can be isolated in SigNoz.

## Native release-proof dashboard

TraceForge ships the definition of a native SigNoz dashboard named **TraceForge — Release Proof** at
[`infra/signoz/traceforge-release-proof.dashboard.json`](../infra/signoz/traceforge-release-proof.dashboard.json).
It has three variables (`run_id`, `phase`, `service_name`) and sixteen panels:

| Panel | Type | Source signal |
| --- | --- | --- |
| Requests observed server-side | value | traces |
| Error spans | value | traces |
| `"database is locked"` logs | value | logs |
| Server-side span P95 | value | traces |
| Request count by phase | graph | traces |
| Error rate by phase | bar | traces |
| Span duration P50 / P95 / P99 | graph | traces |
| HTTP status distribution | pie | traces |
| Lock-error logs by phase | bar | logs |
| Slowest operations | table | traces |
| Correlated traces | list | traces |
| Correlated logs | list | logs |
| TraceForge state-machine stage duration | table | traces |
| SigNoz MCP tool calls | bar | traces |
| SigNoz MCP tool failures | bar | traces |
| TraceForge stage failures | bar | traces |

Every query is built from attributes TraceForge actually emits and that were confirmed present in
the live instance through `signoz_get_field_keys` and `signoz_get_field_values`: `traceforge.run.id`,
`traceforge.phase`, `traceforge.mcp.tool`, `traceforge.success`, `service.name`, `http.status_code`,
and span name. The panels are trace- and log-derived on purpose; the only custom metric series the
target emits is `traceforge.demo.request.duration`, so latency panels read span durations rather than
inventing metric names.

Publish it with:

```bash
uv run traceforge dashboard publish --dry-run   # validate the definition locally
uv run traceforge dashboard publish             # create or replace it in SigNoz through MCP
```

The command discovers the dashboard tools at runtime, looks the title up through
`signoz_list_dashboards`, and then calls `signoz_create_dashboard` or `signoz_update_dashboard`, so
republishing is idempotent rather than duplicating panels.

**Measured permission limitation.** The hosted SigNoz MCP server does expose the write tools
(`signoz_create_dashboard`, `signoz_update_dashboard`, `signoz_delete_dashboard`,
`signoz_import_dashboard`), but a read-only service-account key is refused by the SigNoz API with
`403: only editors/admins can access this resource`. That is the result we get with the least-privilege
key this project recommends, and the CLI reports it verbatim instead of pretending the dashboard was
created. Two supported paths:

1. Run `uv run traceforge dashboard publish` with an editor or admin API key.
2. Import the JSON by hand: **Dashboards → New dashboard → Import JSON**, paste the file contents,
   then set `run_id` to the run you want to inspect.

## Failure semantics

TraceForge uses bounded retries for transient MCP transport errors and bounded polling for delayed
ingestion. It will not silently widen the experiment window to unrelated traffic.

If configuration, authentication, capability discovery, service presence, correlation, or ingestion
fails, the run records `SigNoz verification unavailable` and publishes `NEEDS_REVIEW`. It does not
substitute k6 client measurements for server-side evidence.

## Secret hygiene

- Keep `.env` untracked; `.gitignore` already excludes it.
- Use a service-account API key, rotate it after demos, and never paste it into run input.
- MCP invocation records contain digests and redacted arguments, not authorization headers.
- Ingestion and API keys are read only from the environment.

References: [SigNoz MCP Server documentation](https://signoz.io/docs/ai/signoz-mcp-server/) and the
[official SigNoz MCP Server repository](https://github.com/SigNoz/signoz-mcp-server).
