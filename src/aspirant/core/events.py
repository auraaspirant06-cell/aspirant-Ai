"""Lightweight async pub/sub event bus for internal modules and WebSocket clients."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
from typing import Any


@dataclass(slots=True, frozen=True)
class Event:
    """Structured event broadcast across backend components and UI clients."""

    event_type: str
    payload: dict[str, Any]
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class EventBus:
    """Thread-safe event hub supporting multiple asyncio WebSocket subscribers."""

    def __init__(self, history_limit: int = 100) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[int, tuple[asyncio.AbstractEventLoop, asyncio.Queue[Event]]] = {}
        self._next_id = 1
        self._history: deque[Event] = deque(maxlen=history_limit)

    def subscribe(self, max_queue: int = 64) -> tuple[int, asyncio.Queue[Event]]:
        """Register an async subscriber bound to the caller's running event loop."""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue)
        with self._lock:
            sub_id = self._next_id
            self._next_id += 1
            self._subscribers[sub_id] = (loop, queue)
        return sub_id, queue

    def unsubscribe(self, sub_id: int) -> None:
        """Remove a subscriber safely."""
        with self._lock:
            self._subscribers.pop(sub_id, None)

    def publish(self, event_type: str, payload: dict[str, Any]) -> Event:
        """Publish an event to all subscribers without blocking the emitter."""
        event = Event(event_type=event_type, payload=payload)
        with self._lock:
            self._history.append(event)
            targets = list(self._subscribers.values())

        for loop, queue in targets:
            if loop.is_closed():
                continue
            loop.call_soon_threadsafe(self._enqueue_drop_oldest, queue, event)
        return event

    @staticmethod
    def _enqueue_drop_oldest(queue: asyncio.Queue[Event], event: Event) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent events as serializable dictionaries."""
        with self._lock:
            items = list(self._history)[-limit:]
        return [item.to_dict() for item in items]
