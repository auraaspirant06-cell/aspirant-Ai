"""Add voice_profiles, social_connections, and feedback_events tables.

Revision ID: 0002_voice_integrations_reasoning
Revises: 0001_initial_ecosystem
Create Date: 2026-11-27
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_voice_integrations_reasoning"
down_revision: Union[str, Sequence[str], None] = "0001_initial_ecosystem"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "voice_profiles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(128), nullable=False, server_default="Owner Voice"),
        sa.Column("embedding_json", sa.JSON(), nullable=False),
        sa.Column("voice_unlock_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confidence_threshold", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_voice_profiles_user_id", "voice_profiles", ["user_id"], unique=True)

    op.create_table(
        "social_connections",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("permissions_json", sa.JSON(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_social_connections_user_id", "social_connections", ["user_id"])
    op.create_index("ix_social_connections_platform", "social_connections", ["platform"])

    op.create_table(
        "feedback_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(64), nullable=False, server_default="general"),
        sa.Column("rating", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("correction_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feedback_events_user_id", "feedback_events", ["user_id"])
    op.create_index("ix_feedback_events_created_at", "feedback_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("feedback_events")
    op.drop_table("social_connections")
    op.drop_table("voice_profiles")
