import json
from pathlib import Path

from traceforge.ledger import AuditLedger


def append_complete_ledger(path: Path) -> AuditLedger:
    ledger = AuditLedger(path, "run-1")
    ledger.append(
        previous_state="CREATED",
        next_state="REPOSITORY_VALIDATED",
        action="repository.validate",
        actor_type="system",
        actor_name="test",
        input_value={"path": "repo"},
        output_value={"ok": True},
    )
    ledger.append(
        previous_state="REPOSITORY_VALIDATED",
        next_state="FAILED",
        action="run.failed",
        actor_type="system",
        actor_name="test",
        input_value={},
        output_value={"reason": "test"},
    )
    return ledger


def test_ledger_verifies_hashes_and_terminal(tmp_path: Path) -> None:
    ledger = append_complete_ledger(tmp_path / "run.jsonl")
    result = ledger.verify()
    assert result.valid, result.errors
    assert result.event_count == 2
    assert result.terminal_state == "FAILED"


def test_ledger_tamper_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    ledger = append_complete_ledger(path)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[0]["action"] = "tampered"
    path.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
    result = ledger.verify()
    assert not result.valid
    assert any("hash mismatch" in error for error in result.errors)


def test_missing_terminal_is_invalid_by_default(tmp_path: Path) -> None:
    ledger = AuditLedger(tmp_path / "run.jsonl", "run-1")
    ledger.append(
        previous_state="CREATED",
        next_state="REPOSITORY_VALIDATED",
        action="repository.validate",
        actor_type="system",
        actor_name="test",
        input_value={},
        output_value={},
    )
    result = ledger.verify()
    assert not result.valid
    assert "ledger has no terminal status" in result.errors
