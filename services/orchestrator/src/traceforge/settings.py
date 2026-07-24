from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", enable_decoding=False)

    data_dir: Path = Field(default=Path(".traceforge"), alias="TRACEFORGE_DATA_DIR")
    allowed_repo_roots: list[Path] = Field(
        default_factory=list, alias="TRACEFORGE_ALLOWED_REPO_ROOTS"
    )
    allowed_targets: list[str] = Field(
        default_factory=lambda: ["127.0.0.1", "localhost"], alias="TRACEFORGE_ALLOWED_TARGETS"
    )
    trusted_local_mode: bool = Field(default=False, alias="TRACEFORGE_TRUSTED_LOCAL_MODE")
    web_origin: str = Field(default="http://127.0.0.1:3000", alias="TRACEFORGE_WEB_ORIGIN")

    signoz_region: str | None = Field(default=None, alias="SIGNOZ_REGION")
    signoz_ingestion_key: str | None = Field(default=None, alias="SIGNOZ_INGESTION_KEY")
    signoz_instance_url: str | None = Field(default=None, alias="SIGNOZ_INSTANCE_URL")
    signoz_api_key: str | None = Field(default=None, alias="SIGNOZ_API_KEY")
    signoz_mcp_url: str | None = Field(default=None, alias="SIGNOZ_MCP_URL")
    otlp_endpoint: str | None = Field(default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    otlp_headers: str | None = Field(default=None, alias="OTEL_EXPORTER_OTLP_HEADERS")
    otlp_protocol: str = Field(default="http/protobuf", alias="OTEL_EXPORTER_OTLP_PROTOCOL")
    service_name: str = Field(default="traceforge-orchestrator", alias="OTEL_SERVICE_NAME")

    max_vus: int = 100
    max_duration_seconds: int = 600
    max_subprocess_output_bytes: int = 2_000_000
    subprocess_timeout_seconds: int = 900
    mcp_timeout_seconds: float = 20
    ingestion_timeout_seconds: int = 90

    @field_validator("allowed_repo_roots", mode="before")
    @classmethod
    def split_paths(cls, value: object) -> object:
        if isinstance(value, str):
            if not value.strip():
                return []
            return [Path(part.strip()) for part in value.split(os.pathsep) if part.strip()]
        return value

    @field_validator("allowed_targets", mode="before")
    @classmethod
    def split_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip().lower() for part in value.split(",") if part.strip()]
        return value

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "runs").mkdir(exist_ok=True)
        (self.data_dir / "ledgers").mkdir(exist_ok=True)

    @property
    def signoz_mcp_configured(self) -> bool:
        return bool(self.signoz_mcp_url and self.signoz_instance_url and self.signoz_api_key)

    @property
    def telemetry_ingestion_configured(self) -> bool:
        return bool(self.otlp_endpoint and (self.otlp_headers or self.signoz_ingestion_key))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.allowed_repo_roots:
        settings.allowed_repo_roots = [Path.cwd().resolve()]
    settings.ensure_directories()
    return settings
