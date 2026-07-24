from __future__ import annotations

from pathlib import Path

from traceforge.git_inspector import GitInspector
from traceforge.ledger import digest
from traceforge.models import AuditCheck, Diagnosis, PatchAudit, PatchProposal
from traceforge.process import ProcessError, run_process
from traceforge.security import SecurityViolation, validate_patch_paths


class PatchError(RuntimeError):
    pass


def propose_minimal_reversion(
    inspector: GitInspector,
    *,
    diagnosis: Diagnosis,
    base_sha: str,
    allowed_files: set[str],
) -> PatchProposal:
    if not diagnosis.root_cause_file or diagnosis.root_cause_file not in allowed_files:
        raise PatchError("diagnosis does not identify a changed root-cause file")
    diff = inspector._git(
        "diff",
        "--no-ext-diff",
        "--unified=6",
        diagnosis.first_bad_revision,
        base_sha,
        "--",
        diagnosis.root_cause_file,
    )
    if not diff.strip():
        raise PatchError("no minimal reversion patch could be derived from the diagnosed change")
    files = validate_patch_paths(diff, allowed_files)
    return PatchProposal(
        unified_diff=diff,
        explanation=(
            "Revert only the telemetry-attributed change in the diagnosed file. "
            "The patch is still subject to sandbox application, tests, identical load, "
            "and SigNoz verification."
        ),
        changed_files=files,
        diagnosis_digest=digest(diagnosis.model_dump(mode="json")),
    )


def audit_patch(
    proposal: PatchProposal,
    *,
    worktree: Path,
    allowed_files: set[str],
    evidence_available: bool,
) -> PatchAudit:
    checks: list[AuditCheck] = []
    try:
        changed = validate_patch_paths(proposal.unified_diff, allowed_files)
        checks.append(AuditCheck(name="scope", passed=True, detail=", ".join(changed)))
    except SecurityViolation as exc:
        checks.append(AuditCheck(name="scope", passed=False, detail=str(exc)))
    patch_path = worktree / ".traceforge-proposal.diff"
    patch_path.write_text(proposal.unified_diff, encoding="utf-8", newline="\n")
    try:
        run_process(
            ["git", "apply", "--check", str(patch_path)],
            cwd=worktree,
            timeout_seconds=30,
        )
        checks.append(AuditCheck(name="applies_cleanly", passed=True, detail="git apply --check"))
    except ProcessError as exc:
        checks.append(AuditCheck(name="applies_cleanly", passed=False, detail=str(exc)))
    checks.append(
        AuditCheck(
            name="signoz_grounding",
            passed=evidence_available,
            detail=(
                "diagnosis cites retrieved SigNoz evidence"
                if evidence_available
                else "SigNoz evidence is unavailable"
            ),
        )
    )
    checks.append(
        AuditCheck(
            name="reversible",
            passed=proposal.reversible,
            detail="proposal is a unified diff and can be reverse-applied",
        )
    )
    return PatchAudit(
        passed=all(check.passed for check in checks),
        checks=checks,
        auditor="traceforge-deterministic-auditor",
    )


def apply_patch(proposal: PatchProposal, *, worktree: Path) -> None:
    patch_path = worktree / ".traceforge-proposal.diff"
    patch_path.write_text(proposal.unified_diff, encoding="utf-8", newline="\n")
    try:
        run_process(["git", "apply", str(patch_path)], cwd=worktree, timeout_seconds=30)
    except ProcessError as exc:
        raise PatchError(str(exc)) from exc
