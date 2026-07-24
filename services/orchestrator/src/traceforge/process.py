from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


class ProcessError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProcessResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def run_process(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = 120,
    max_output_bytes: int = 2_000_000,
    check: bool = True,
) -> ProcessResult:
    if not args or any("\x00" in arg for arg in args):
        raise ProcessError("invalid subprocess arguments")
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    try:
        completed = subprocess.run(  # noqa: S603 - argv is passed without a shell
            list(args),
            cwd=cwd,
            env=process_env,
            capture_output=True,
            text=False,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise ProcessError(f"required executable not found: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProcessError(f"process timed out after {timeout_seconds}s: {args[0]}") from exc
    stdout_bytes = completed.stdout[:max_output_bytes]
    stderr_bytes = completed.stderr[:max_output_bytes]
    result = ProcessResult(
        args=tuple(args),
        returncode=completed.returncode,
        stdout=stdout_bytes.decode("utf-8", errors="replace"),
        stderr=stderr_bytes.decode("utf-8", errors="replace"),
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-2_000:]
        raise ProcessError(f"{args[0]} exited {result.returncode}: {detail}")
    return result
