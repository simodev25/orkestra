"""SkillDefinition entity."""

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SkillDefinition(BaseModel):
    __tablename__ = "skill_definitions"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    behavior_templates: Mapped[list] = mapped_column(JSONB, default=list)
    output_guidelines: Mapped[list] = mapped_column(JSONB, default=list)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    status: Mapped[str] = mapped_column(String(20), default="active")
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    skill_families = relationship("SkillFamily", back_populates="skill", cascade="all, delete-orphan")
    agent_skills = relationship("AgentSkill", back_populates="skill")
