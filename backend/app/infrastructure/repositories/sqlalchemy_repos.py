"""Concrete SQLAlchemy 2.0 repository implementations with transparent encryption at rest."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import EncryptionAtRest
from backend.app.domain.entities import (
    AgentRunEntity,
    AuditEventEntity,
    GoalEntity,
    HabitEntity,
    MemoryEntity,
    MemoryLayer,
    NoteEntity,
    ProductSource,
    RefreshSessionEntity,
    ReminderEntity,
    UserEntity,
)
from backend.app.infrastructure.db.models import (
    AgentRunModel,
    AuditLogModel,
    GoalModel,
    HabitModel,
    MemoryModel,
    NoteModel,
    RefreshSessionModel,
    ReminderModel,
    UserModel,
)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SQLAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(row: UserModel) -> UserEntity:
        return UserEntity(
            id=row.id,
            email=row.email,
            full_name=row.full_name,
            password_hash=row.password_hash,
            role=row.role,
            is_active=row.is_active,
            preferences=dict(row.preferences_json or {}),
            profile_summary=row.profile_summary,
            created_at=_ensure_utc(row.created_at),
        )

    async def create(self, user: UserEntity) -> UserEntity:
        row = UserModel(
            id=user.id,
            email=user.email.lower().strip(),
            full_name=user.full_name,
            password_hash=user.password_hash,
            role=user.role,
            is_active=user.is_active,
            preferences_json=user.preferences,
            profile_summary=user.profile_summary,
            created_at=user.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_entity(row)

    async def get_by_id(self, user_id: str) -> UserEntity | None:
        row = await self._session.get(UserModel, user_id)
        return self._to_entity(row) if row else None

    async def get_by_email(self, email: str) -> UserEntity | None:
        stmt = select(UserModel).where(UserModel.email == email.lower().strip())
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def update_preferences(
        self, user_id: str, preferences: dict, profile_summary: str | None = None
    ) -> UserEntity | None:
        row = await self._session.get(UserModel, user_id)
        if not row:
            return None
        merged = dict(row.preferences_json or {})
        merged.update(preferences)
        row.preferences_json = merged
        if profile_summary is not None:
            row.profile_summary = profile_summary
        await self._session.flush()
        return self._to_entity(row)


class SQLAlchemySessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, entity: RefreshSessionEntity) -> RefreshSessionEntity:
        row = RefreshSessionModel(
            id=entity.id,
            user_id=entity.user_id,
            token_hash=entity.token_hash,
            device_name=entity.device_name,
            device_platform=entity.device_platform,
            revoked=entity.revoked,
            expires_at=entity.expires_at,
            created_at=entity.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return entity

    async def get_by_id(self, session_id: str) -> RefreshSessionEntity | None:
        row = await self._session.get(RefreshSessionModel, session_id)
        if not row:
            return None
        return RefreshSessionEntity(
            id=row.id,
            user_id=row.user_id,
            token_hash=row.token_hash,
            device_name=row.device_name,
            device_platform=row.device_platform,
            revoked=row.revoked,
            expires_at=_ensure_utc(row.expires_at),
            created_at=_ensure_utc(row.created_at),
        )

    async def revoke(self, session_id: str) -> None:
        await self._session.execute(
            update(RefreshSessionModel).where(RefreshSessionModel.id == session_id).values(revoked=True)
        )

    async def revoke_all_for_user(self, user_id: str) -> int:
        result = await self._session.execute(
            update(RefreshSessionModel)
            .where(RefreshSessionModel.user_id == user_id, RefreshSessionModel.revoked.is_(False))
            .values(revoked=True)
        )
        return int(result.rowcount or 0)


class SQLAlchemyMemoryRepository:
    def __init__(self, session: AsyncSession, crypto: EncryptionAtRest) -> None:
        self._session = session
        self._crypto = crypto

    def _to_entity(self, row: MemoryModel) -> MemoryEntity:
        return MemoryEntity(
            id=row.id,
            user_id=row.user_id,
            layer=MemoryLayer(row.layer),
            content=self._crypto.decrypt(row.content_encrypted),
            summary=row.summary,
            source_app=ProductSource(row.source_app),
            tags=list(row.tags_json or []),
            importance=float(row.importance),
            metadata=dict(row.metadata_json or {}),
            created_at=_ensure_utc(row.created_at),
            updated_at=_ensure_utc(row.updated_at),
        )

    async def add(self, item: MemoryEntity) -> MemoryEntity:
        row = MemoryModel(
            id=item.id,
            user_id=item.user_id,
            layer=item.layer.value,
            content_encrypted=self._crypto.encrypt(item.content),
            summary=item.summary,
            source_app=item.source_app.value,
            tags_json=item.tags,
            importance=item.importance,
            metadata_json=item.metadata,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_entity(row)

    async def list_for_user(
        self, user_id: str, *, layer: MemoryLayer | None = None, limit: int = 50
    ) -> list[MemoryEntity]:
        stmt = select(MemoryModel).where(MemoryModel.user_id == user_id)
        if layer is not None:
            stmt = stmt.where(MemoryModel.layer == layer.value)
        stmt = stmt.order_by(desc(MemoryModel.created_at)).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(r) for r in rows]

    async def search_text(self, user_id: str, query: str, limit: int = 10) -> list[MemoryEntity]:
        all_items = await self.list_for_user(user_id, limit=250)
        needle = query.lower().strip()
        if not needle:
            return all_items[:limit]
        terms = [t for t in needle.split() if t]
        scored: list[tuple[int, MemoryEntity]] = []
        for item in all_items:
            hay = f"{item.content} {item.summary} {' '.join(item.tags)}".lower()
            score = sum(1 for term in terms if term in hay)
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda pair: (pair[0], pair[1].importance), reverse=True)
        return [item for _, item in scored[:limit]]

    async def delete(self, user_id: str, memory_id: str) -> bool:
        result = await self._session.execute(
            delete(MemoryModel).where(MemoryModel.id == memory_id, MemoryModel.user_id == user_id)
        )
        return bool(result.rowcount)


class SQLAlchemyProductivityRepository:
    def __init__(self, session: AsyncSession, crypto: EncryptionAtRest) -> None:
        self._session = session
        self._crypto = crypto

    async def upsert_goal(self, goal: GoalEntity) -> GoalEntity:
        existing = await self._session.get(GoalModel, goal.id)
        if existing:
            existing.title = goal.title
            existing.description = goal.description
            existing.status = goal.status
            existing.progress = goal.progress
            existing.target_date = goal.target_date
            existing.milestones_json = goal.milestones
        else:
            existing = GoalModel(
                id=goal.id,
                user_id=goal.user_id,
                title=goal.title,
                description=goal.description,
                status=goal.status,
                progress=goal.progress,
                target_date=goal.target_date,
                milestones_json=goal.milestones,
            )
            self._session.add(existing)
        await self._session.flush()
        return GoalEntity(
            id=existing.id,
            user_id=existing.user_id,
            title=existing.title,
            description=existing.description,
            status=existing.status,
            progress=existing.progress,
            target_date=existing.target_date,
            milestones=list(existing.milestones_json or []),
            updated_at=_ensure_utc(existing.updated_at),
        )

    async def list_goals(self, user_id: str) -> list[GoalEntity]:
        stmt = select(GoalModel).where(GoalModel.user_id == user_id).order_by(desc(GoalModel.updated_at))
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            GoalEntity(
                id=r.id,
                user_id=r.user_id,
                title=r.title,
                description=r.description,
                status=r.status,
                progress=r.progress,
                target_date=r.target_date,
                milestones=list(r.milestones_json or []),
                updated_at=_ensure_utc(r.updated_at),
            )
            for r in rows
        ]

    async def upsert_habit(self, habit: HabitEntity) -> HabitEntity:
        existing = await self._session.get(HabitModel, habit.id)
        if existing:
            existing.title = habit.title
            existing.cadence = habit.cadence
            existing.streak = habit.streak
            existing.last_completed_on = habit.last_completed_on
        else:
            existing = HabitModel(
                id=habit.id,
                user_id=habit.user_id,
                title=habit.title,
                cadence=habit.cadence,
                streak=habit.streak,
                last_completed_on=habit.last_completed_on,
            )
            self._session.add(existing)
        await self._session.flush()
        return HabitEntity(
            id=existing.id,
            user_id=existing.user_id,
            title=existing.title,
            cadence=existing.cadence,
            streak=existing.streak,
            last_completed_on=existing.last_completed_on,
            updated_at=_ensure_utc(existing.updated_at),
        )

    async def list_habits(self, user_id: str) -> list[HabitEntity]:
        stmt = select(HabitModel).where(HabitModel.user_id == user_id).order_by(desc(HabitModel.updated_at))
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            HabitEntity(
                id=r.id,
                user_id=r.user_id,
                title=r.title,
                cadence=r.cadence,
                streak=r.streak,
                last_completed_on=r.last_completed_on,
                updated_at=_ensure_utc(r.updated_at),
            )
            for r in rows
        ]

    async def upsert_reminder(self, reminder: ReminderEntity) -> ReminderEntity:
        existing = await self._session.get(ReminderModel, reminder.id)
        if existing:
            existing.title = reminder.title
            existing.due_at = reminder.due_at
            existing.channel = reminder.channel
            existing.completed = reminder.completed
            existing.context_note = reminder.context_note
        else:
            existing = ReminderModel(
                id=reminder.id,
                user_id=reminder.user_id,
                title=reminder.title,
                due_at=reminder.due_at,
                channel=reminder.channel,
                completed=reminder.completed,
                context_note=reminder.context_note,
            )
            self._session.add(existing)
        await self._session.flush()
        return ReminderEntity(
            id=existing.id,
            user_id=existing.user_id,
            title=existing.title,
            due_at=existing.due_at,
            channel=existing.channel,
            completed=existing.completed,
            context_note=existing.context_note,
            updated_at=_ensure_utc(existing.updated_at),
        )

    async def list_reminders(self, user_id: str) -> list[ReminderEntity]:
        stmt = (
            select(ReminderModel)
            .where(ReminderModel.user_id == user_id)
            .order_by(desc(ReminderModel.updated_at))
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            ReminderEntity(
                id=r.id,
                user_id=r.user_id,
                title=r.title,
                due_at=r.due_at,
                channel=r.channel,
                completed=r.completed,
                context_note=r.context_note,
                updated_at=_ensure_utc(r.updated_at),
            )
            for r in rows
        ]

    async def upsert_note(self, note: NoteEntity) -> NoteEntity:
        existing = await self._session.get(NoteModel, note.id)
        enc = self._crypto.encrypt(note.content)
        if existing:
            existing.title = note.title
            existing.content_encrypted = enc
            existing.ai_summary = note.ai_summary
            existing.tags_json = note.tags
            existing.source_app = note.source_app.value
        else:
            existing = NoteModel(
                id=note.id,
                user_id=note.user_id,
                title=note.title,
                content_encrypted=enc,
                ai_summary=note.ai_summary,
                tags_json=note.tags,
                source_app=note.source_app.value,
            )
            self._session.add(existing)
        await self._session.flush()
        return NoteEntity(
            id=existing.id,
            user_id=existing.user_id,
            title=existing.title,
            content=self._crypto.decrypt(existing.content_encrypted),
            ai_summary=existing.ai_summary,
            tags=list(existing.tags_json or []),
            source_app=ProductSource(existing.source_app),
            updated_at=_ensure_utc(existing.updated_at),
        )

    async def list_notes(self, user_id: str) -> list[NoteEntity]:
        stmt = select(NoteModel).where(NoteModel.user_id == user_id).order_by(desc(NoteModel.updated_at))
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            NoteEntity(
                id=r.id,
                user_id=r.user_id,
                title=r.title,
                content=self._crypto.decrypt(r.content_encrypted),
                ai_summary=r.ai_summary,
                tags=list(r.tags_json or []),
                source_app=ProductSource(r.source_app),
                updated_at=_ensure_utc(r.updated_at),
            )
            for r in rows
        ]


class SQLAlchemyAgentRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_run(self, run: AgentRunEntity) -> AgentRunEntity:
        row = AgentRunModel(
            id=run.id,
            user_id=run.user_id,
            objective=run.objective,
            source_app=run.source_app.value,
            selected_agents_json=run.selected_agents,
            plan_steps_json=run.plan_steps,
            final_output=run.final_output,
            status=run.status,
            created_at=run.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return run

    async def list_runs(self, user_id: str, limit: int = 25) -> list[AgentRunEntity]:
        stmt = (
            select(AgentRunModel)
            .where(AgentRunModel.user_id == user_id)
            .order_by(desc(AgentRunModel.created_at))
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            AgentRunEntity(
                id=r.id,
                user_id=r.user_id,
                objective=r.objective,
                source_app=ProductSource(r.source_app),
                selected_agents=list(r.selected_agents_json or []),
                plan_steps=list(r.plan_steps_json or []),
                final_output=r.final_output,
                status=r.status,
                created_at=_ensure_utc(r.created_at),
            )
            for r in rows
        ]


class SQLAlchemyAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log_event(self, event: AuditEventEntity) -> AuditEventEntity:
        row = AuditLogModel(
            id=event.id,
            user_id=event.user_id,
            action=event.action,
            resource=event.resource,
            outcome=event.outcome,
            ip_address=event.ip_address,
            details_json=event.details,
            created_at=event.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return event

    async def list_events(self, user_id: str | None = None, limit: int = 100) -> list[AuditEventEntity]:
        stmt = select(AuditLogModel)
        if user_id is not None:
            stmt = stmt.where(AuditLogModel.user_id == user_id)
        stmt = stmt.order_by(desc(AuditLogModel.created_at)).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            AuditEventEntity(
                id=r.id,
                user_id=r.user_id,
                action=r.action,
                resource=r.resource,
                outcome=r.outcome,
                ip_address=r.ip_address,
                details=dict(r.details_json or {}),
                created_at=_ensure_utc(r.created_at),
            )
            for r in rows
        ]
