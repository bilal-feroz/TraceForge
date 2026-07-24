# TraceForge demo target

This FastAPI/SQLite service is the source template for the generated demonstration repository.
Run `python scripts/bootstrap_demo_repo.py` from the TraceForge repository root to create real Git
history containing the baseline, lock regression, silent-latency regression, and control refs.

Every request accepts TraceForge correlation headers and adds them to application spans, metrics,
and structured logs. Without OTLP configuration it still runs locally, but TraceForge will report
`SigNoz verification unavailable` and will not issue a SHIP verdict that depends on telemetry.

