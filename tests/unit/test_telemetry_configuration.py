from traceforge.settings import Settings
from traceforge.telemetry import _headers, _signal_endpoint


def test_signal_endpoint_appends_otlp_http_path() -> None:
    base = "https://ingest.example.test:443/"

    assert _signal_endpoint(base, "traces") == "https://ingest.example.test:443/v1/traces"
    assert _signal_endpoint(base, "metrics") == "https://ingest.example.test:443/v1/metrics"


def test_settings_builds_private_target_telemetry_environment() -> None:
    settings = Settings(
        _env_file=None,
        OTEL_EXPORTER_OTLP_ENDPOINT="https://ingest.example.test:443",
        SIGNOZ_INGESTION_KEY="private-test-key",
        OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf",
    )

    environment = settings.telemetry_environment()

    assert environment == {
        "OTEL_EXPORTER_OTLP_ENDPOINT": "https://ingest.example.test:443",
        "OTEL_EXPORTER_OTLP_HEADERS": "signoz-ingestion-key=private-test-key",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    }


def test_explicit_otlp_headers_take_precedence() -> None:
    headers = _headers("signoz-ingestion-key=header-key", "fallback-key")

    assert headers == {"signoz-ingestion-key": "header-key"}
