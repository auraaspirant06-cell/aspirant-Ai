"""Domain entities for the Aspirant AI Ecosystem (Clean Architecture core)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class MemoryLayer(StrEnum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    PREFERENCE = "preference"
    KNOWLEDGE = "knowledge"
    CONVERSATION = "conversation"


class AgentRole(StrEnum):
    RESEARCH = "research"
    AUTOMATION = "automation"
    CODING = "coding"
    CONTENT = "content"
    PRODUCTIVITY = "productivity"
    PLANNING = "planning"
    SUPPORT = "support"


class ProductSource(StrEnum):
    NOVA = "nova"
    MJ = "mj"
    MAX = "max"
    WEB = "web"


@dataclass(slots=True)
class UserEntity:
    id: str
    email: str
    full_name: str
    password_hash: str
    role: str = "owner"
    is_active: bool = True
    preferences: dict[str, Any] = field(default_factory=dict)
    profile_summary: str = ""
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class RefreshSessionEntity:
    id: str
    user_id: str
    token_hash: str
    device_name: str
    device_platform: str
    revoked: bool = False
    expires_at: datetime = field(default_factory=utc_now)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class MemoryEntity:
    id: str
    user_id: str
    layer: MemoryLayer
    content: str
    summary: str = ""
    source_app: ProductSource = ProductSource.MJ
    tags: list[str] = field(default_factory=list)
    importance: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class GoalEntity:
    id: str
    user_id: str
    title: str
    description: str = ""
    status: str = "active"
    progress: int = 0
    target_date: str | None = None
    milestones: list[dict[str, Any]] = field(default_factory=list)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class HabitEntity:
    id: str
    user_id: str
    title: str
    cadence: str = "daily"
    streak: int = 0
    last_completed_on: str | None = None
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class ReminderEntity:
    id: str
    user_id: str
    title: str
    due_at: str
    channel: str = "push"
    completed: bool = False
    context_note: str = ""
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class NoteEntity:
    id: str
    user_id: str
    title: str
    content: str
    ai_summary: str = ""
    tags: list[str] = field(default_factory=list)
    source_app: ProductSource = ProductSource.MAX
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class AgentRunEntity:
    id: str
    user_id: str
    objective: str
    source_app: ProductSource
    selected_agents: list[str]
    plan_steps: list[dict[str, Any]]
    final_output: str
    status: str = "completed"
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class AuditEventEntity:
    id: str
    user_id: str | None
    action: str
    resource: str
    outcome: str
    ip_address: str = "local"
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
