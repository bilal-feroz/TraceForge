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
