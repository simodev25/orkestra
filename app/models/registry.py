"""AgentDefinition and MCPDefinition entities."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import AgentStatus, MCPStatus


class AgentDefinition(BaseModel):
    __tablename__ = "agent_definitions"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    family_id: Mapped[str] = mapped_column(String(50), ForeignKey("family_definitions.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    selection_hints: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    allowed_mcps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    forbidden_effects: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    input_contract_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_contract_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    criticality: Mapped[str] = mapped_column(String(20), default="medium")
    cost_profile: Mapped[str] = mapped_column(String(20), default="medium")
    limitations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    prompt_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    skills_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    soul_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)  # "ollama" or "openai"
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)     # model name
    allow_code_execution: Mapped[bool] = mapped_column(Boolean, default=False)    # enable execute_python_code tool
    last_test_status: Mapped[str] = mapped_column(String(30), default="not_tested")
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    status: Mapped[str] = mapped_column(String(20), default=AgentStatus.DRAFT)
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    family_rel = relationship("FamilyDefinition", back_populates="agents")
    agent_skills = relationship("AgentSkill", back_populates="agent", cascade="all, delete-orphan")


class MCPDefinition(BaseModel):
    __tablename__ = "mcp_definitions"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    purpose: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    effect_type: Mapped[str] = mapped_column(String(30))
    input_contract_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_contract_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    allowed_agents: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    criticality: Mapped[str] = mapped_column(String(20), default="medium")
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    retry_policy: Mapped[str] = mapped_column(String(30), default="standard")
    cost_profile: Mapped[str] = mapped_column(String(20), default="low")
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    audit_required: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default=MCPStatus.DRAFT)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
