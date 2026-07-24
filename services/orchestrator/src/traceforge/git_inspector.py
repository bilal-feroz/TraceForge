from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

from traceforge.models import ChangedFile, ChangeSet, GitRevision
from traceforge.process import ProcessError, run_process
from traceforge.security import SecurityViolation

_SAFE_REF = re.compile(r"^[A-Za-z0-9._/@{}+\-^~:]+$")


class GitInspectionError(RuntimeError):
    pass


class GitInspector:
    def __init__(self, repository: Path) -> None:
        self.repository = repository.resolve()
        top_level = self._git("rev-parse", "--show-toplevel").strip()
        if Path(top_level).resolve() != self.repository:
            raise SecurityViolation(
                f"repository path must be the Git top level ({Path(top_level).resolve()})"
            )

    def _git(self, *args: str, timeout: int = 60) -> str:
        try:
            return run_process(["git", *args], cwd=self.repository, timeout_seconds=timeout).stdout
        except ProcessError as exc:
            raise GitInspectionError(str(exc)) from exc

    @staticmethod
    def _validate_ref(ref: str) -> str:
        if not _SAFE_REF.fullmatch(ref) or ref.startswith("-"):
            raise SecurityViolation(f"unsafe Git ref: {ref!r}")
        return ref

    def revision(self, ref: str) -> GitRevision:
        safe_ref = self._validate_ref(ref)
        record = self._git(
            "show",
            "-s",
            "--format=%H%x00%s%x00%aI",
            "--no-patch",
            safe_ref,
        ).strip()
        parts = record.split("\x00")
        if len(parts) != 3:
            raise GitInspectionError(f"unexpected Git metadata for {safe_ref}")
        return GitRevision(
            ref=ref,
            sha=parts[0],
            subject=parts[1],
            author_time=datetime.fromisoformat(parts[2]),
        )

    def inspect(self, base_ref: str, candidate_ref: str) -> ChangeSet:
        base = self.revision(base_ref)
        candidate = self.revision(candidate_ref)
        merge_base = self._git("merge-base", base.sha, candidate.sha).strip()
        diff = self._git(
            "diff",
            "--no-ext-diff",
            "--unified=12",
            "--find-renames",
            base.sha,
            candidate.sha,
            timeout=120,
        )
        status_lines = self._git(
            "diff", "--numstat", "--find-renames", base.sha, candidate.sha
        ).splitlines()
        name_status = self._git(
            "diff", "--name-status", "--find-renames", base.sha, candidate.sha
        ).splitlines()
        statuses: dict[str, str] = {}
        for line in name_status:
            parts = line.split("\t")
            if len(parts) >= 2:
                statuses[parts[-1].replace("\\", "/")] = parts[0]
        files: list[ChangedFile] = []
        for line in status_lines:
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            path = parts[-1].replace("\\", "/")
            additions = int(parts[0]) if parts[0].isdigit() else 0
            deletions = int(parts[1]) if parts[1].isdigit() else 0
            files.append(
                ChangedFile(
                    path=path,
                    status=statuses.get(path, "M"),
                    additions=additions,
                    deletions=deletions,
                )
            )
        return ChangeSet(
            base=base,
            candidate=candidate,
            merge_base_sha=merge_base,
            files=files,
            unified_diff=diff,
            diff_digest=hashlib.sha256(diff.encode("utf-8")).hexdigest(),
        )

    def file_at(self, ref: str, relative_path: str) -> str:
        safe_ref = self._validate_ref(ref)
        normalized = relative_path.replace("\\", "/")
        if normalized.startswith("/") or ".." in Path(normalized).parts:
            raise SecurityViolation(f"unsafe repository path: {relative_path}")
        return self._git("show", f"{safe_ref}:{normalized}")

    def list_files(self, ref: str) -> list[str]:
        safe_ref = self._validate_ref(ref)
        output = self._git("ls-tree", "-r", "--name-only", safe_ref)
        return [line.strip() for line in output.splitlines() if line.strip()]
