from pathlib import Path

import pytest

from traceforge.settings import Settings


def test_documented_allowlist_formats_are_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRACEFORGE_ALLOWED_REPO_ROOTS", r"C:\work;D:\repositories")
    monkeypatch.setenv("TRACEFORGE_ALLOWED_TARGETS", "127.0.0.1,localhost")

    settings = Settings(_env_file=None)

    assert settings.allowed_repo_roots == [Path(r"C:\work"), Path(r"D:\repositories")]
    assert settings.allowed_targets == ["127.0.0.1", "localhost"]
