from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import DEPLOYMENT_ENVIRONMENT, SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_configured = False


def _headers() -> dict[str, str]:
    value = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
    headers: dict[str, str] = {}
    for item in value.split(","):
        if "=" not in item:
            continue
        key, raw = item.split("=", 1)
        if key.strip():
            headers[key.strip()] = raw.strip()
    ingestion_key = os.getenv("SIGNOZ_INGESTION_KEY")
    if ingestion_key and "signoz-ingestion-key" not in headers:
        headers["signoz-ingestion-key"] = ingestion_key
    return headers


def configure_telemetry(service_name: str, service_version: str = "0.1.0") -> bool:
    global _configured
    if _configured:
        return True
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return False

    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    resource = Resource.create(
        {
            SERVICE_NAME: service_name,
            "service.version": service_version,
            DEPLOYMENT_ENVIRONMENT: os.getenv("TRACEFORGE_ENVIRONMENT", "preproduction"),
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(headers=_headers())))
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(headers=_headers()),
        export_interval_millis=10_000,
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
    _configured = True
    return True


def instrument_fastapi(app: Any) -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        return
    FastAPIInstrumentor.instrument_app(app)


def get_tracer(name: str = "traceforge") -> trace.Tracer:
    return trace.get_tracer(name)


def get_meter(name: str = "traceforge") -> metrics.Meter:
    return metrics.get_meter(name)


@contextmanager
def workflow_span(name: str, **attributes: Any) -> Iterator[trace.Span]:
    tracer = get_tracer("traceforge.workflow")
    clean_attributes = {
        key: value
        for key, value in attributes.items()
        if value is not None and isinstance(value, str | bool | int | float)
    }
    with tracer.start_as_current_span(name, attributes=clean_attributes) as span:
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_attribute("traceforge.success", False)
            raise
        else:
            span.set_attribute("traceforge.success", True)


def attach_correlation(attributes: dict[str, str]) -> None:
    span = trace.get_current_span()
    if not span.is_recording():
        return
    for key, value in attributes.items():
        if value:
            span.set_attribute(key, value)


def configure_structured_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format=(
            '{"timestamp":"%(asctime)s","severity":"%(levelname)s",'
            '"logger":"%(name)s","message":"%(message)s"}'
        ),
    )
