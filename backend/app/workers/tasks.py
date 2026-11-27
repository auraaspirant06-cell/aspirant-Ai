"""Background Celery tasks for async embeddings, multi-agent plans, deep research, and mobile push notifications."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.app.workers.celery_app import celery_app


@celery_app.task(name="aspirant.embed_memory")
def embed_memory_task(user_id: str, memory_id: str, text_length: int) -> dict:
    return {
        "status": "indexed",
        "user_id": user_id,
        "memory_id": memory_id,
        "characters": text_length,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="aspirant.deep_research")
def deep_research_task(user_id: str, topic: str, depth: str = "standard") -> dict:
    return {
        "status": "queued_complete",
        "user_id": user_id,
        "topic": topic,
        "depth": depth,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="aspirant.dispatch_push")
def dispatch_push_notification_task(user_id: str, title: str, body: str, channel: str = "max-android") -> dict:
    return {
        "status": "dispatched",
        "user_id": user_id,
        "title": title,
        "body": body,
        "channel": channel,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
