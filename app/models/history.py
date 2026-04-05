"""Version history for families, skills, and agents."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class AgentDefinitionHistory(Base):
    """Snapshot of an AgentDefinition at a previous version."""
    __tablename__ = "agent_definition_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(String(100), ForeignKey("agent_definitions.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    family_id: Mapped[str] = mapped_column(String(50), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_ids_snapshot: Mapped[list] = mapped_column(JSONB, default=list)
    prompt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    soul_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    selection_hints: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    allowed_mcps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    forbidden_effects: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    limitations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    criticality: Mapped[str] = mapped_column(String(20), nullable=False)
    cost_profile: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    replaced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    original_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FamilyDefinitionHistory(Base):
    """Snapshot of a FamilyDefinition at a previous version."""
    __tablename__ = "family_definition_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    family_id: Mapped[str] = mapped_column(String(50), ForeignKey("family_definitions.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_system_rules: Mapped[list] = mapped_column(JSONB, default=list)
    default_forbidden_effects: Mapped[list] = mapped_column(JSONB, default=list)
    default_output_expectations: Mapped[list] = mapped_column(JSONB, default=list)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    replaced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    original_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SkillDefinitionHistory(Base):
    """Snapshot of a SkillDefinition at a previous version."""
    __tablename__ = "skill_definition_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    skill_id: Mapped[str] = mapped_column(String(100), ForeignKey("skill_definitions.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    behavior_templates: Mapped[list] = mapped_column(JSONB, default=list)
    output_guidelines: Mapped[list] = mapped_column(JSONB, default=list)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Store allowed_families as snapshot (list of family_ids at that point in time)
    allowed_families_snapshot: Mapped[list] = mapped_column(JSONB, default=list)
    replaced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    original_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
