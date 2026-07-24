from __future__ import annotations

import logging
import os

from opentelemetry import metrics, trace
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_configured = False


def _headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "").split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            headers[key.strip()] = value.strip()
    key = os.getenv("SIGNOZ_INGESTION_KEY")
    if key and "signoz-ingestion-key" not in headers:
        headers["signoz-ingestion-key"] = key
    return headers


def configure_telemetry(service_name: str, service_version: str) -> bool:
    global _configured
    if _configured:
        return True
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    logging.basicConfig(
        level=logging.INFO,
        format='{"timestamp":"%(asctime)s","severity":"%(levelname)s","message":"%(message)s"}',
    )
    if not endpoint:
        return False

    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "deployment.environment": "preproduction",
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(headers=_headers()),
            schedule_delay_millis=1_000,
        )
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(headers=_headers()),
        export_interval_millis=5_000,
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(
            OTLPLogExporter(headers=_headers()),
            schedule_delay_millis=1_000,
        )
    )
    logging.getLogger().addHandler(
        LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    )
    # The app object is instrumented after construction in instrument_app().
    globals()["_fastapi_instrumentor"] = FastAPIInstrumentor
    _configured = True
    return True


def instrument_app(app: object) -> None:
    instrumentor = globals().get("_fastapi_instrumentor")
    if instrumentor is not None:
        instrumentor.instrument_app(app)
