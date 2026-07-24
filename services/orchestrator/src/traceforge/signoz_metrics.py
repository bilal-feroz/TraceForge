from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from traceforge.models import MetricEvidence
from traceforge.security import redact


def _objects(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _objects(nested)


def _timestamp(value: Any) -> datetime | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 100_000_000_000_000_000:
        number /= 1_000_000_000
    elif number > 100_000_000_000:
        number /= 1_000
    try:
        return datetime.fromtimestamp(number, tz=UTC)
    except (OSError, OverflowError, ValueError):
        return None


def _point(value: Any) -> tuple[datetime, float] | None:
    if isinstance(value, list | tuple) and len(value) >= 2:
        raw_time, raw_value = value[0], value[1]
    elif isinstance(value, dict):
        raw_time = value.get("timestamp", value.get("time"))
        raw_value = value.get("value")
    else:
        return None
    timestamp = _timestamp(raw_time)
    try:
        number = float(raw_value)
    except (TypeError, ValueError):
        return None
    if timestamp is None:
        return None
    return timestamp, number


def metric_evidence(value: Any, *, default_name: str) -> list[MetricEvidence]:
    """Normalize common SigNoz/Prometheus series envelopes without assuming one server version."""
    evidence: list[MetricEvidence] = []
    seen: set[str] = set()
    for row in _objects(value):
        raw_points = row.get("values", row.get("points"))
        if not isinstance(raw_points, list):
            continue
        points = [point for item in raw_points if (point := _point(item)) is not None]
        if not points:
            continue
        metric = row.get("metric")
        labels = metric if isinstance(metric, dict) else row.get("labels", {})
        if not isinstance(labels, dict):
            labels = {}
        name = str(
            labels.get("__name__") or row.get("metricName") or row.get("name") or default_name
        )
        attributes = redact(labels)
        key = json.dumps(
            {
                "name": name,
                "attributes": attributes,
                "points": [(point[0].isoformat(), point[1]) for point in points],
            },
            sort_keys=True,
            default=str,
        )
        if key in seen:
            continue
        seen.add(key)
        evidence.append(
            MetricEvidence(
                name=name,
                unit=str(row["unit"]) if row.get("unit") is not None else None,
                points=points,
                attributes=attributes,
            )
        )
    return evidence
