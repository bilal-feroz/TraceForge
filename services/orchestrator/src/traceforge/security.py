from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from traceforge.settings import Settings

_SENSITIVE_KEY = re.compile(
    r"(authorization|api[-_]?key|token|secret|password|cookie|ingestion[-_]?key)",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{16,}|"
    r"(?:api[-_]?key|token|secret|password)\s*[:=]\s*[\"']?[^\s,\"']{8,})"
)


class SecurityViolation(ValueError):
    pass


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def validate_repository_path(path: Path, settings: Settings) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise SecurityViolation(f"repository path is not a directory: {resolved}")
    if not any(is_within(resolved, root) for root in settings.allowed_repo_roots):
        roots = ", ".join(str(root.resolve()) for root in settings.allowed_repo_roots)
        raise SecurityViolation(f"repository is outside allowed roots: {roots}")
    if not (resolved / ".git").exists():
        raise SecurityViolation(f"path is not a Git repository: {resolved}")
    return resolved


def validate_target_url(url: str, settings: Settings) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SecurityViolation("target URL must use http or https")
    if not parsed.hostname:
        raise SecurityViolation("target URL has no hostname")
    host = parsed.hostname.lower()
    if host not in settings.allowed_targets:
        raise SecurityViolation(
            f"target host {host!r} is not allowlisted; default targets are loopback only"
        )
    if parsed.username or parsed.password:
        raise SecurityViolation("credentials are not allowed in target URLs")
    return url.rstrip("/")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "<redacted>" if _SENSITIVE_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return _SECRET_VALUE.sub("<redacted>", value)
    return value


def contains_secret(text: str) -> bool:
    return bool(_SECRET_VALUE.search(text))


def validate_patch_paths(diff: str, allowed_files: set[str]) -> list[str]:
    changed: list[str] = []
    for line in diff.splitlines():
        if not line.startswith("+++ b/"):
            continue
        path = line[6:].strip().replace("\\", "/")
        if path == "/dev/null":
            continue
        if path.startswith("/") or ".." in Path(path).parts:
            raise SecurityViolation(f"unsafe patch path: {path}")
        if path not in allowed_files and not path.startswith("tests/"):
            raise SecurityViolation(f"patch modifies file outside diagnosis scope: {path}")
        changed.append(path)
    if not changed:
        raise SecurityViolation("patch contains no changed files")
    if contains_secret(diff):
        raise SecurityViolation("patch appears to contain a credential or secret")
    return changed
