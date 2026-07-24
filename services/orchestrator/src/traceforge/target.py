from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import BinaryIO

import httpx

from traceforge.security import SecurityViolation
from traceforge.settings import Settings

ALLOWED_EXECUTABLES = {"python", "python3", "uv", "uvicorn"}


class TargetProcessError(RuntimeError):
    pass


class TargetProcess:
    def __init__(
        self,
        *,
        command: list[str],
        cwd: Path,
        target_url: str,
        log_path: Path,
        settings: Settings,
        environment: dict[str, str] | None = None,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.target_url = target_url
        self.log_path = log_path
        self.settings = settings
        self.environment = environment or {}
        self.process: subprocess.Popen[bytes] | None = None
        self._log_handle: BinaryIO | None = None

    def _validate(self) -> None:
        if not self.settings.trusted_local_mode:
            raise SecurityViolation(
                "target process startup requires TRACEFORGE_TRUSTED_LOCAL_MODE=true"
            )
        if not self.command:
            raise SecurityViolation("target command is empty")
        executable = Path(self.command[0]).name.lower()
        if executable.endswith(".exe"):
            executable = executable[:-4]
        if executable not in ALLOWED_EXECUTABLES:
            raise SecurityViolation(
                f"target executable {executable!r} is not in the local command allowlist"
            )
        if any(arg in {"-c", "--eval", "-e"} for arg in self.command[1:]):
            raise SecurityViolation("inline code execution is not allowed in target commands")

    def start(self, *, timeout_seconds: float = 30) -> None:
        self._validate()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_handle = self.log_path.open("wb")
        env = os.environ.copy()
        env.update(self.settings.telemetry_environment())
        env.update(self.environment)
        self.process = subprocess.Popen(  # noqa: S603 - executable and flags are allowlisted
            self.command,
            cwd=self.cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            shell=False,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        health_url = f"{self.target_url.rstrip('/')}/health"
        deadline = time.monotonic() + timeout_seconds
        last_error = "target did not answer"
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self._flush_log()
                detail = self.log_path.read_text(encoding="utf-8", errors="replace")[-2_000:]
                raise TargetProcessError(f"target exited with {self.process.returncode}: {detail}")
            try:
                response = httpx.get(health_url, timeout=1)
                if response.status_code < 500:
                    return
                last_error = f"health endpoint returned {response.status_code}"
            except httpx.HTTPError as exc:
                last_error = str(exc)
            time.sleep(0.25)
        self.stop()
        raise TargetProcessError(f"target startup timed out: {last_error}")

    def _flush_log(self) -> None:
        if self._log_handle:
            self._log_handle.flush()

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self._flush_log()
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None
        self.process = None

    def __enter__(self) -> TargetProcess:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
