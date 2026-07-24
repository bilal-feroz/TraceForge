from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class RunEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def publish(self, run_id: str, event: dict[str, Any]) -> None:
        self._history[run_id].append(event)
        for queue in list(self._subscribers[run_id]):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue

    def history(self, run_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(run_id, []))

    def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
        self._subscribers[run_id].add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers[run_id].discard(queue)


event_bus = RunEventBus()
