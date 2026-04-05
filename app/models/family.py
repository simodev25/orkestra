"""FamilyDefinition, SkillFamily, and AgentSkill entities."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.core.database import Base


class FamilyDefinition(BaseModel):
    __tablename__ = "family_definitions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    skill_families = relationship("SkillFamily", back_populates="family", cascade="all, delete-orphan")
    agents = relationship("AgentDefinition", back_populates="family_rel")


class SkillFamily(Base):
    """Join table: which skills are allowed for which families."""
    __tablename__ = "skill_families"

    skill_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("skill_definitions.id", ondelete="CASCADE"), primary_key=True
    )
    family_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("family_definitions.id", ondelete="CASCADE"), primary_key=True
    )

    skill = relationship("SkillDefinition", back_populates="skill_families")
    family = relationship("FamilyDefinition", back_populates="skill_families")


class AgentSkill(Base):
    """Join table: which skills an agent uses."""
    __tablename__ = "agent_skills"

    agent_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("agent_definitions.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("skill_definitions.id", ondelete="RESTRICT"), primary_key=True
    )

    agent = relationship("AgentDefinition", back_populates="agent_skills")
    skill = relationship("SkillDefinition", back_populates="agent_skills")
