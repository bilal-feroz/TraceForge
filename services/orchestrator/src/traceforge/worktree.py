from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from traceforge.process import ProcessError, run_process
from traceforge.security import is_within


class WorktreeError(RuntimeError):
    pass


@dataclass(slots=True)
class Worktree:
    repository: Path
    path: Path
    revision: str
    managed_root: Path
    active: bool = False

    def create(self) -> Path:
        resolved_root = self.managed_root.resolve()
        resolved_path = self.path.resolve()
        if not is_within(resolved_path, resolved_root) or resolved_path == resolved_root:
            raise WorktreeError("worktree target is outside the managed run directory")
        resolved_root.mkdir(parents=True, exist_ok=True)
        if resolved_path.exists():
            if any(resolved_path.iterdir()):
                raise WorktreeError(f"worktree target is not empty: {resolved_path}")
            resolved_path.rmdir()
        try:
            run_process(
                ["git", "worktree", "add", "--detach", str(resolved_path), self.revision],
                cwd=self.repository,
                timeout_seconds=120,
            )
        except ProcessError as exc:
            raise WorktreeError(str(exc)) from exc
        self.active = True
        return resolved_path

    def remove(self) -> None:
        if not self.active:
            return
        resolved_path = self.path.resolve()
        resolved_root = self.managed_root.resolve()
        if not is_within(resolved_path, resolved_root) or resolved_path == resolved_root:
            raise WorktreeError("refusing to remove an unmanaged worktree path")
        try:
            run_process(
                ["git", "worktree", "remove", "--force", str(resolved_path)],
                cwd=self.repository,
                timeout_seconds=120,
            )
        except ProcessError as exc:
            raise WorktreeError(str(exc)) from exc
        finally:
            self.active = False
        if resolved_path.exists():
            shutil.rmtree(resolved_path)

    def __enter__(self) -> Path:
        return self.create()

    def __exit__(self, *_: object) -> None:
        self.remove()
