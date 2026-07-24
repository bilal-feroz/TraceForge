from pathlib import Path

import app as target


def test_database_initialization(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(target, "DB_PATH", tmp_path / "demo.db")
    target.init_db()
    assert target.DB_PATH.exists()


def test_health_is_stable() -> None:
    response = target.health()
    assert response["status"] == "ok"
    assert response["service"] == target.SERVICE_NAME


def test_event_store_is_bounded() -> None:
    target.event_values.clear()
    target.event_total = 0
    for value in range(1_100):
        result = target.create_event(target.EventIn(value=value % 10))
    assert result["retained"] == 1_000
    assert len(target.event_values) == 1_000
