from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path
from uuid import uuid4

from traceforge.database import RunStore
from traceforge.diagnosis import generate_diagnosis
from traceforge.endpoints import EndpointExtractor
from traceforge.events import RunEventBus, event_bus
from traceforge.git_inspector import GitInspector
from traceforge.k6 import execute, render_script, validate_script
from traceforge.ledger import AuditLedger, LedgerVerification
from traceforge.load_plan import choose_endpoint, create_plan
from traceforge.models import (
    K6RunResult,
    PatchVerificationStatus,
    Phase,
    RegressionClassification,
    RepositoryTarget,
    Stage,
    TerminalState,
    TraceForgeRun,
    Verdict,
    VerdictValue,
    VerificationResult,
    utc_now,
)
from traceforge.patching import (
    PatchError,
    apply_patch,
    audit_patch,
    propose_minimal_reversion,
)
from traceforge.process import ProcessError, run_process
from traceforge.regression import assess_regression
from traceforge.release_proof import ReleaseProof, build_release_proof
from traceforge.security import (
    SecurityViolation,
    validate_repository_path,
    validate_target_url,
)
from traceforge.settings import Settings, get_settings
from traceforge.signoz import SigNozMCPClient, SigNozUnavailable, unavailable_evidence
from traceforge.state_machine import IllegalTransition, StateMachine
from traceforge.target import TargetProcess
from traceforge.telemetry import workflow_span
from traceforge.worktree import Worktree


class RunNotFound(KeyError):
    pass


class RunEngine:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        store: RunStore | None = None,
        events: RunEventBus | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.store = store or RunStore(self.settings.data_dir / "traceforge.sqlite3")
        self.events = events or event_bus

    def _ledger(self, run_id: str) -> AuditLedger:
        return AuditLedger(self.settings.data_dir / "ledgers" / f"{run_id}.jsonl", run_id)

    def _run_dir(self, run_id: str) -> Path:
        path = self.settings.data_dir / "runs" / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def create(self, target: RepositoryTarget) -> TraceForgeRun:
        run_id = str(uuid4())
        now = utc_now()
        run = TraceForgeRun(
            run_id=run_id,
            target=target,
            stage=Stage.CREATED,
            created_at=now,
            updated_at=now,
        )
        self.store.save(run)
        self.events.publish(
            run_id,
            {
                "type": "run.created",
                "run_id": run_id,
                "stage": Stage.CREATED.value,
                "timestamp": now.isoformat(),
            },
        )
        return run

    def get(self, run_id: str) -> TraceForgeRun:
        run = self.store.get(run_id)
        if run is None:
            raise RunNotFound(run_id)
        return run

    def _transition(
        self,
        run: TraceForgeRun,
        next_state: Stage | TerminalState,
        *,
        action: str,
        output: object,
        evidence_ids: list[str] | None = None,
    ) -> bool:
        event_id = f"{run.run_id}:{next_state.value}"
        if self.store.transition_exists(event_id):
            return False
        current = run.terminal_state or run.stage
        machine = StateMachine(state=current)
        result = machine.transition(event_id, next_state)
        occurred = utc_now()
        inserted = self.store.record_transition(
            event_id=event_id,
            run_id=run.run_id,
            previous_state=result.previous,
            next_state=result.current,
            occurred_at=occurred,
            outcome="success",
        )
        if not inserted:
            return False
        self._ledger(run.run_id).append(
            previous_state=result.previous.value,
            next_state=result.current.value,
            action=action,
            actor_type="system",
            actor_name="traceforge-state-machine",
            tool_name=None,
            input_value={"event_id": event_id},
            output_value=output,
            evidence_ids=evidence_ids,
        )
        if isinstance(next_state, Stage):
            run.stage = next_state
        else:
            run.terminal_state = next_state
        run.updated_at = occurred
        self.store.save(run)
        self.events.publish(
            run.run_id,
            {
                "type": "state.transition",
                "event_id": event_id,
                "previous_state": result.previous.value,
                "next_state": result.current.value,
                "action": action,
                "timestamp": occurred.isoformat(),
            },
        )
        return True

    async def analyze(self, run_id: str) -> TraceForgeRun:
        run = self.get(run_id)
        if run.terminal_state is not None:
            return run
        try:
            return await self._analyze(run)
        except asyncio.CancelledError:
            self._terminate(run, TerminalState.CANCELLED, "run.cancelled")
            raise
        except Exception as exc:
            run.last_error = str(exc)
            self.store.save(run)
            self.events.publish(
                run.run_id,
                {"type": "run.error", "error": str(exc), "timestamp": utc_now().isoformat()},
            )
            self._terminate(run, TerminalState.FAILED, "run.failed")
            return run

    async def _analyze(self, run: TraceForgeRun) -> TraceForgeRun:
        repository = Path(run.target.path)
        run_dir = self._run_dir(run.run_id)

        if run.stage == Stage.CREATED:
            with workflow_span("repository.inspect", **{"traceforge.run.id": run.run_id}):
                repository = validate_repository_path(repository, self.settings)
                validate_target_url(str(run.target.target_url), self.settings)
                inspector = GitInspector(repository)
                inspector.revision(run.target.base_ref)
                inspector.revision(run.target.candidate_ref)
            self._transition(
                run,
                Stage.REPOSITORY_VALIDATED,
                action="repository.validate",
                output={"repository": str(repository)},
            )

        inspector = GitInspector(repository)
        if run.stage == Stage.REPOSITORY_VALIDATED:
            with workflow_span("change.read", **{"traceforge.run.id": run.run_id}):
                run.change_set = await asyncio.to_thread(
                    inspector.inspect, run.target.base_ref, run.target.candidate_ref
                )
                (run_dir / "change.diff").write_text(
                    run.change_set.unified_diff, encoding="utf-8", newline="\n"
                )
            self.store.save(run)
            self._transition(
                run,
                Stage.CHANGE_INSPECTED,
                action="change.inspect",
                output={"diff_digest": run.change_set.diff_digest},
            )

        if run.stage == Stage.CHANGE_INSPECTED:
            assert run.change_set
            with workflow_span("endpoint.extract", **{"traceforge.run.id": run.run_id}):
                run.endpoints = await asyncio.to_thread(
                    EndpointExtractor(inspector).extract, run.change_set
                )
                if not run.endpoints:
                    raise ValueError("no affected API endpoint was discovered")
            self.store.save(run)
            self._transition(
                run,
                Stage.ENDPOINTS_SCOPED,
                action="endpoints.scope",
                output=[item.model_dump(mode="json") for item in run.endpoints],
            )

        if run.stage == Stage.ENDPOINTS_SCOPED:
            endpoint = choose_endpoint(run.endpoints)
            with workflow_span("load.plan.generate", **{"traceforge.run.id": run.run_id}):
                run.load_plan = create_plan(
                    endpoint,
                    profile=run.target.profile,
                    target_url=str(run.target.target_url),
                )
            self.store.save(run)
            self._transition(
                run,
                Stage.LOAD_PLAN_CREATED,
                action="load.plan.create",
                output=run.load_plan.model_dump(mode="json"),
            )

        if run.stage == Stage.LOAD_PLAN_CREATED:
            assert run.load_plan
            with workflow_span("k6.script.render", **{"traceforge.run.id": run.run_id}):
                script = render_script(run.load_plan, run_dir / "load-test.js")
            with workflow_span("k6.script.validate", **{"traceforge.run.id": run.run_id}):
                run.k6_script = await asyncio.to_thread(validate_script, script, self.settings)
            self.store.save(run)
            if not run.k6_script.validated:
                raise RuntimeError(run.k6_script.validation_error or "k6 validation failed")
            self._transition(
                run,
                Stage.K6_SCRIPT_VALIDATED,
                action="k6.script.validate",
                output=run.k6_script.model_dump(mode="json"),
            )

        if run.stage == Stage.K6_SCRIPT_VALIDATED:
            assert run.change_set
            result = await asyncio.to_thread(
                self._experiment,
                run,
                Phase.BASELINE,
                run.change_set.base.sha,
            )
            run.experiments[Phase.BASELINE] = result
            self.store.save(run)
            self._transition(
                run,
                Stage.BASELINE_COMPLETED,
                action="baseline.execute",
                output=result.model_dump(mode="json"),
            )

        if run.stage == Stage.BASELINE_COMPLETED:
            assert run.change_set
            result = await asyncio.to_thread(
                self._experiment,
                run,
                Phase.CANDIDATE,
                run.change_set.candidate.sha,
            )
            run.experiments[Phase.CANDIDATE] = result
            self.store.save(run)
            self._transition(
                run,
                Stage.CANDIDATE_COMPLETED,
                action="candidate.execute",
                output=result.model_dump(mode="json"),
            )

        if run.stage == Stage.CANDIDATE_COMPLETED:
            with workflow_span("signoz.preflight", **{"traceforge.run.id": run.run_id}):
                await self._retrieve_telemetry(run)
            if not all(
                run.telemetry.get(phase) and run.telemetry[phase].available
                for phase in (Phase.BASELINE, Phase.CANDIDATE)
            ):
                self._publish(
                    run,
                    VerdictValue.NEEDS_REVIEW,
                    "SigNoz verification unavailable; client load was measured but "
                    "server-side evidence could not be confirmed.",
                )
                return run
            self._transition(
                run,
                Stage.TELEMETRY_CONFIRMED,
                action="signoz.telemetry.confirm",
                output={"phases": ["baseline", "candidate"]},
                evidence_ids=[
                    trace.trace_id
                    for evidence in run.telemetry.values()
                    for trace in evidence.traces[:20]
                ],
            )

        if run.stage == Stage.TELEMETRY_CONFIRMED:
            with workflow_span("telemetry.correlate", **{"traceforge.run.id": run.run_id}):
                trace_count = sum(len(item.traces) for item in run.telemetry.values())
                log_count = sum(len(item.logs) for item in run.telemetry.values())
            self._transition(
                run,
                Stage.SIGNALS_CORRELATED,
                action="telemetry.correlate",
                output={"trace_count": trace_count, "log_count": log_count},
            )

        if run.stage == Stage.SIGNALS_CORRELATED:
            baseline = run.experiments[Phase.BASELINE]
            candidate = run.experiments[Phase.CANDIDATE]
            with workflow_span("regression.classify", **{"traceforge.run.id": run.run_id}) as span:
                run.assessment = assess_regression(
                    baseline,
                    candidate,
                    candidate_evidence=run.telemetry[Phase.CANDIDATE],
                )
                span.set_attribute("traceforge.classification", run.assessment.classification.value)
            assert run.change_set and run.load_plan
            with workflow_span("diagnosis.generate", **{"traceforge.run.id": run.run_id}):
                run.diagnosis = generate_diagnosis(
                    change=run.change_set,
                    assessment=run.assessment,
                    evidence=run.telemetry[Phase.CANDIDATE],
                    endpoint=run.load_plan.endpoint.path,
                )
            self.store.save(run)
            self._transition(
                run,
                Stage.REGRESSION_CLASSIFIED,
                action="regression.classify",
                output=run.assessment.model_dump(mode="json"),
            )

        if run.stage == Stage.REGRESSION_CLASSIFIED:
            assert run.assessment
            if run.assessment.classification == RegressionClassification.NO_REGRESSION:
                with workflow_span("verification.execute", **{"traceforge.run.id": run.run_id}):
                    await asyncio.to_thread(self._verify_control, run)
                return run
            if run.assessment.classification == RegressionClassification.INSUFFICIENT_EVIDENCE:
                self._publish(
                    run,
                    VerdictValue.NEEDS_REVIEW,
                    "The deterministic assessment found insufficient evidence.",
                )
                return run
            await asyncio.to_thread(self._propose_and_audit, run, inspector)

        if run.stage == Stage.PATCH_AUDITED:
            if not run.patch_audit or not run.patch_audit.passed:
                self._publish(
                    run,
                    VerdictValue.NEEDS_REVIEW,
                    "The proposed patch did not pass independent audit.",
                )
                return run
            with workflow_span("verification.execute", **{"traceforge.run.id": run.run_id}):
                await self._verify_patch(run)
        return run

    def _experiment(self, run: TraceForgeRun, phase: Phase, revision: str) -> K6RunResult:
        assert run.k6_script
        run_dir = self._run_dir(run.run_id)
        artifact_dir = run_dir / "experiments" / phase.value
        if not run.target.target_command:
            with workflow_span(
                "k6.execute",
                **{"traceforge.run.id": run.run_id, "traceforge.phase": phase.value},
            ):
                return execute(
                    script=run.k6_script,
                    phase=phase,
                    run_id=run.run_id,
                    git_sha=revision,
                    target_url=str(run.target.target_url),
                    artifact_dir=artifact_dir,
                    settings=self.settings,
                )
        worktree = Worktree(
            repository=Path(run.target.path),
            path=run_dir / "worktrees" / phase.value,
            revision=revision,
            managed_root=run_dir / "worktrees",
        )
        with worktree as worktree_path:
            with TargetProcess(
                command=run.target.target_command,
                cwd=worktree_path,
                target_url=str(run.target.target_url),
                log_path=artifact_dir / "target.log",
                settings=self.settings,
                environment={
                    "TRACEFORGE_GIT_SHA": revision,
                    "OTEL_SERVICE_NAME": "traceforge-demo-target",
                    "PYTHONUNBUFFERED": "1",
                },
            ):
                with workflow_span(
                    "k6.execute",
                    **{"traceforge.run.id": run.run_id, "traceforge.phase": phase.value},
                ):
                    return execute(
                        script=run.k6_script,
                        phase=phase,
                        run_id=run.run_id,
                        git_sha=revision,
                        target_url=str(run.target.target_url),
                        artifact_dir=artifact_dir,
                        settings=self.settings,
                    )

    async def _retrieve_telemetry(self, run: TraceForgeRun) -> None:
        assert run.load_plan
        for phase in (Phase.BASELINE, Phase.CANDIDATE):
            result = run.experiments[phase]
            client = SigNozMCPClient(
                self.settings,
                invocation_sink=lambda item: self.store.save_mcp_invocation(
                    run.run_id, item.model_dump(mode="json")
                ),
            )
            try:
                evidence = await client.investigate(
                    run_id=run.run_id,
                    service_name="traceforge-demo-target",
                    endpoint=run.load_plan.endpoint.path,
                    window=result.window,
                )
            except SigNozUnavailable as exc:
                evidence = unavailable_evidence(
                    run_id=run.run_id,
                    service_name="traceforge-demo-target",
                    endpoint=run.load_plan.endpoint.path,
                    window=result.window,
                    reason=str(exc),
                    phase=phase,
                )
            run.telemetry[phase] = evidence
            self.events.publish(
                run.run_id,
                {
                    "type": "telemetry.phase",
                    "phase": phase.value,
                    "available": evidence.available,
                    "reason": evidence.unavailable_reason,
                    "timestamp": utc_now().isoformat(),
                },
            )
        self.store.save(run)

    def _test_worktree(self, path: Path) -> bool:
        if not self.settings.trusted_local_mode:
            return False
        has_tests = (path / "tests").is_dir() or any(path.glob("test_*.py"))
        if not has_tests:
            return False
        try:
            run_process(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=path,
                timeout_seconds=180,
                max_output_bytes=self.settings.max_subprocess_output_bytes,
            )
        except ProcessError:
            return False
        return True

    def _verify_control(self, run: TraceForgeRun) -> None:
        assert run.change_set and run.assessment
        run_dir = self._run_dir(run.run_id)
        worktree = Worktree(
            repository=Path(run.target.path),
            path=run_dir / "worktrees" / "control-tests",
            revision=run.change_set.candidate.sha,
            managed_root=run_dir / "worktrees",
        )
        with worktree as path:
            tests_passed = self._test_worktree(path)
        baseline = run.experiments[Phase.BASELINE]
        candidate = run.experiments[Phase.CANDIDATE]
        same_script = baseline.script_digest == candidate.script_digest
        if not tests_passed:
            status = PatchVerificationStatus.TESTS_FAILED
            risks = ["candidate tests did not pass"]
        elif not same_script:
            status = PatchVerificationStatus.MANUAL_REVIEW_REQUIRED
            risks = ["baseline and candidate did not use the same load script"]
        elif not candidate.successful or candidate.stats.threshold_failures:
            status = PatchVerificationStatus.VERIFIED_REGRESSION
            risks = ["candidate violated a load threshold"]
        else:
            status = PatchVerificationStatus.VERIFIED_NO_CHANGE
            risks = []
        run.verification = VerificationResult(
            status=status,
            baseline=baseline,
            candidate=candidate,
            patched=None,
            assessment=run.assessment,
            tests_passed=tests_passed,
            telemetry_complete=True,
            same_script_digest=same_script,
            remaining_risks=risks,
        )
        self.store.save(run)
        self._transition(
            run,
            Stage.VERIFICATION_COMPLETED,
            action="control.verify",
            output=run.verification.model_dump(mode="json"),
        )
        if status == PatchVerificationStatus.VERIFIED_NO_CHANGE:
            self._publish(
                run, VerdictValue.SHIP, "No regression was measured and candidate tests pass."
            )
        elif status in {
            PatchVerificationStatus.TESTS_FAILED,
            PatchVerificationStatus.VERIFIED_REGRESSION,
        }:
            self._publish(
                run,
                VerdictValue.BLOCK,
                "Candidate verification failed a deterministic test or load gate.",
            )
        else:
            self._publish(
                run,
                VerdictValue.NEEDS_REVIEW,
                "No regression was measured, but experiment equivalence was not proven.",
            )

    def _propose_and_audit(self, run: TraceForgeRun, inspector: GitInspector) -> None:
        assert run.change_set and run.diagnosis
        allowed = {item.path for item in run.change_set.files}
        with workflow_span("patch.generate", **{"traceforge.run.id": run.run_id}):
            run.patch = propose_minimal_reversion(
                inspector,
                diagnosis=run.diagnosis,
                base_sha=run.change_set.base.sha,
                allowed_files=allowed,
            )
        self.store.save(run)
        self._transition(
            run,
            Stage.PATCH_PROPOSED,
            action="patch.propose",
            output={"files": run.patch.changed_files},
        )
        run_dir = self._run_dir(run.run_id)
        worktree = Worktree(
            repository=Path(run.target.path),
            path=run_dir / "worktrees" / "audit",
            revision=run.change_set.candidate.sha,
            managed_root=run_dir / "worktrees",
        )
        with worktree as path, workflow_span("patch.audit", **{"traceforge.run.id": run.run_id}):
            run.patch_audit = audit_patch(
                run.patch,
                worktree=path,
                allowed_files=allowed,
                evidence_available=run.telemetry[Phase.CANDIDATE].available,
            )
        self.store.save(run)
        self._transition(
            run,
            Stage.PATCH_AUDITED,
            action="patch.audit",
            output=run.patch_audit.model_dump(mode="json"),
        )

    async def _verify_patch(self, run: TraceForgeRun) -> None:
        assert run.change_set and run.patch and run.k6_script
        run_dir = self._run_dir(run.run_id)
        worktree = Worktree(
            repository=Path(run.target.path),
            path=run_dir / "worktrees" / "patched",
            revision=run.change_set.candidate.sha,
            managed_root=run_dir / "worktrees",
        )
        with worktree as path:
            apply_patch(run.patch, worktree=path)
            tests_passed = self._test_worktree(path)
            self._transition(
                run,
                Stage.PATCH_SANDBOXED,
                action="patch.sandbox",
                output={"tests_passed": tests_passed},
            )
            if not tests_passed:
                run.verification = VerificationResult(
                    status=PatchVerificationStatus.TESTS_FAILED,
                    baseline=run.experiments[Phase.BASELINE],
                    candidate=run.experiments[Phase.CANDIDATE],
                    patched=None,
                    assessment=None,
                    tests_passed=False,
                    telemetry_complete=False,
                    same_script_digest=True,
                    remaining_risks=["sandbox tests failed"],
                )
            else:
                if not run.target.target_command:
                    raise PatchError("patched target startup command is not configured")
                artifact_dir = run_dir / "experiments" / Phase.PATCHED.value
                with TargetProcess(
                    command=run.target.target_command,
                    cwd=path,
                    target_url=str(run.target.target_url),
                    log_path=artifact_dir / "target.log",
                    settings=self.settings,
                    environment={
                        "TRACEFORGE_GIT_SHA": run.change_set.candidate.sha,
                        "OTEL_SERVICE_NAME": "traceforge-demo-target",
                        "PYTHONUNBUFFERED": "1",
                    },
                ):
                    with workflow_span(
                        "k6.execute",
                        **{
                            "traceforge.run.id": run.run_id,
                            "traceforge.phase": Phase.PATCHED.value,
                        },
                    ):
                        patched = await asyncio.to_thread(
                            execute,
                            script=run.k6_script,
                            phase=Phase.PATCHED,
                            run_id=run.run_id,
                            git_sha=run.change_set.candidate.sha,
                            target_url=str(run.target.target_url),
                            artifact_dir=artifact_dir,
                            settings=self.settings,
                        )
                run.experiments[Phase.PATCHED] = patched
                client = SigNozMCPClient(self.settings)
                try:
                    patched_evidence = await client.investigate(
                        run_id=run.run_id,
                        service_name="traceforge-demo-target",
                        endpoint=run.load_plan.endpoint.path if run.load_plan else "",
                        window=patched.window,
                    )
                except SigNozUnavailable as exc:
                    patched_evidence = unavailable_evidence(
                        run_id=run.run_id,
                        service_name="traceforge-demo-target",
                        endpoint=run.load_plan.endpoint.path if run.load_plan else "",
                        window=patched.window,
                        reason=str(exc),
                        phase=Phase.PATCHED,
                    )
                run.telemetry[Phase.PATCHED] = patched_evidence
                assessment = assess_regression(
                    run.experiments[Phase.BASELINE],
                    patched,
                    candidate_evidence=patched_evidence,
                )
                candidate = run.experiments[Phase.CANDIDATE]
                p95_improvement = candidate.stats.p95_ms - patched.stats.p95_ms
                error_improvement = candidate.stats.failure_rate - patched.stats.failure_rate
                materially_improved = (
                    p95_improvement >= max(25, candidate.stats.p95_ms * 0.15)
                    or error_improvement >= 0.01
                )
                telemetry_complete = patched_evidence.available
                same_script = (
                    run.experiments[Phase.BASELINE].script_digest
                    == candidate.script_digest
                    == patched.script_digest
                )
                thresholds_passed = patched.successful and not patched.stats.threshold_failures
                if not telemetry_complete:
                    status = PatchVerificationStatus.TELEMETRY_INCOMPLETE
                    risks = ["patched SigNoz evidence is incomplete"]
                elif not same_script:
                    status = PatchVerificationStatus.MANUAL_REVIEW_REQUIRED
                    risks = ["the patched phase did not use the identical load script"]
                elif (
                    not thresholds_passed
                    or assessment.classification != RegressionClassification.NO_REGRESSION
                ):
                    status = PatchVerificationStatus.VERIFIED_REGRESSION
                    risks = ["the patched phase still violates deterministic regression gates"]
                elif materially_improved:
                    status = PatchVerificationStatus.VERIFIED_IMPROVEMENT
                    risks = []
                else:
                    status = PatchVerificationStatus.VERIFIED_NO_CHANGE
                    risks = ["the patch did not produce a material improvement"]
                run.verification = VerificationResult(
                    status=status,
                    baseline=run.experiments[Phase.BASELINE],
                    candidate=candidate,
                    patched=patched,
                    assessment=assessment,
                    tests_passed=True,
                    telemetry_complete=telemetry_complete,
                    same_script_digest=same_script,
                    remaining_risks=risks,
                )
        self.store.save(run)
        assert run.verification
        self._transition(
            run,
            Stage.VERIFICATION_COMPLETED,
            action="verification.compare",
            output=run.verification.model_dump(mode="json"),
        )
        if run.verification.status == PatchVerificationStatus.VERIFIED_IMPROVEMENT:
            self._publish(
                run,
                VerdictValue.SHIP,
                "Sandbox tests and identical load show a SigNoz-confirmed improvement.",
            )
        elif run.verification.status in {
            PatchVerificationStatus.TESTS_FAILED,
            PatchVerificationStatus.VERIFIED_REGRESSION,
        }:
            self._publish(
                run,
                VerdictValue.BLOCK,
                "The sandbox proof failed a deterministic test, threshold, or regression gate.",
            )
        else:
            self._publish(
                run,
                VerdictValue.NEEDS_REVIEW,
                "The patch was not eligible for SHIP because proof is incomplete or inconclusive.",
            )

    def _publish(self, run: TraceForgeRun, value: VerdictValue, reason: str) -> None:
        with workflow_span(
            "verdict.publish",
            **{"traceforge.run.id": run.run_id, "traceforge.verdict": value.value},
        ):
            run.verdict = Verdict(
                value=value,
                reason=reason,
                verification_status=run.verification.status if run.verification else None,
            )
            self.store.save(run)
            self._transition(
                run,
                Stage.VERDICT_PUBLISHED,
                action="verdict.publish",
                output=run.verdict.model_dump(mode="json"),
            )
            terminal = {
                VerdictValue.SHIP: TerminalState.PASSED,
                VerdictValue.BLOCK: TerminalState.BLOCKED,
                VerdictValue.NEEDS_REVIEW: TerminalState.NEEDS_REVIEW,
            }[value]
            self._transition(
                run,
                terminal,
                action="run.terminal",
                output={"verdict": value.value},
            )

    def _terminate(self, run: TraceForgeRun, terminal: TerminalState, action: str) -> None:
        if run.terminal_state is not None:
            return
        try:
            self._transition(run, terminal, action=action, output={"error": run.last_error})
        except IllegalTransition:
            return

    def cancel(self, run_id: str) -> TraceForgeRun:
        run = self.get(run_id)
        self._terminate(run, TerminalState.CANCELLED, "run.cancel")
        return run

    def ledger_verify(self, run_id: str) -> LedgerVerification:
        self.get(run_id)
        return self._ledger(run_id).verify(require_terminal=True)

    def release_proof(self, run_id: str) -> ReleaseProof:
        run = self.get(run_id)
        return build_release_proof(run, self._ledger(run_id))

    def patch_text(self, run_id: str) -> str:
        run = self.get(run_id)
        if run.patch is None:
            raise PatchError("run has no patch proposal")
        return run.patch.unified_diff

    def cleanup_stale_worktrees(self, run_id: str) -> None:
        run_dir = self._run_dir(run_id)
        worktrees = run_dir / "worktrees"
        if not worktrees.exists():
            return
        run_process(["git", "worktree", "prune"], cwd=Path(self.get(run_id).target.path))
        if worktrees.resolve().parent != run_dir.resolve():
            raise SecurityViolation("refusing to clean an unmanaged worktree directory")
        shutil.rmtree(worktrees)
