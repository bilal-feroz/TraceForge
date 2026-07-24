from pathlib import Path

import pytest

from traceforge.security import (
    SecurityViolation,
    contains_secret,
    redact,
    validate_patch_paths,
    validate_target_url,
)
from traceforge.settings import Settings


def settings(tmp_path: Path) -> Settings:
    return Settings(
        TRACEFORGE_DATA_DIR=tmp_path,
        TRACEFORGE_ALLOWED_REPO_ROOTS=str(tmp_path),
        TRACEFORGE_ALLOWED_TARGETS="localhost,127.0.0.1",
    )


def test_target_url_defaults_to_loopback(tmp_path: Path) -> None:
    assert validate_target_url("http://localhost:8000", settings(tmp_path))
    with pytest.raises(SecurityViolation):
        validate_target_url("https://example.com", settings(tmp_path))


def test_redaction_removes_sensitive_keys_and_values() -> None:
    safe = redact({"SIGNOZ_API_KEY": "secret-value", "message": "token=abcdefghijk"})
    assert safe["SIGNOZ_API_KEY"] == "<redacted>"
    assert "abcdefghijk" not in safe["message"]
    assert contains_secret("api_key=abcdefghijk")


def test_patch_scope_rejects_unrelated_file() -> None:
    diff = "diff --git a/config.py b/config.py\n--- a/config.py\n+++ b/config.py\n"
    with pytest.raises(SecurityViolation):
        validate_patch_paths(diff, {"app.py"})


def test_patch_scope_accepts_diagnosed_file_and_tests() -> None:
    diff = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "diff --git a/tests/test_app.py b/tests/test_app.py\n"
        "--- a/tests/test_app.py\n+++ b/tests/test_app.py\n"
    )
    changed = validate_patch_paths(diff, {"app.py"})
    assert changed == ["app.py", "tests/test_app.py"]
