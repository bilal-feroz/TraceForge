FROM grafana/k6:2.1.0 AS k6

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=k6 /usr/bin/k6 /usr/local/bin/k6
WORKDIR /workspace
COPY pyproject.toml README.md ./
COPY services/orchestrator ./services/orchestrator
RUN pip install --no-cache-dir .
EXPOSE 8787
CMD ["uvicorn", "traceforge.api:app", "--host", "0.0.0.0", "--port", "8787"]
