from __future__ import annotations

import sys
from pathlib import Path

from traceforge.engine import RunEngine
from traceforge.process import ProcessResult
from traceforge.settings import Settings


def test_sandbox_tests_use_active_project_interpreter(
    tmp_path: Path, monkeypatch: object
) -> None:
    worktree = tmp_path / "worktree"
    (worktree / "tests").mkdir(parents=True)
    observed: list[str] = []

    def fake_run_process(args: list[str], **_: object) -> ProcessResult:
        observed.extend(args)
        return ProcessResult(tuple(args), 0, "", "")

    monkeypatch.setattr("traceforge.engine.run_process", fake_run_process)  # type: ignore[attr-defined]
    settings = Settings(
        _env_file=None,
        TRACEFORGE_DATA_DIR=tmp_path / "data",
        TRACEFORGE_TRUSTED_LOCAL_MODE=True,
    )

    assert RunEngine(settings)._test_worktree(worktree)
    assert observed[:4] == [sys.executable, "-m", "pytest", "-q"]
