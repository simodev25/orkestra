"""Local Orkestra governance bindings for Obot MCP servers."""

from sqlalchemy import String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class OrkestraMCPBinding(Base, TimestampMixin):
    __tablename__ = "orkestra_mcp_bindings"

    obot_server_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    obot_server_name: Mapped[str] = mapped_column(String(255))
    enabled_in_orkestra: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden_from_catalog: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_agent_families: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    allowed_workflows: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    business_domain: Mapped[str | None] = mapped_column(String(120), nullable=True)
    risk_level_override: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_use_cases: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    hidden_from_ai_generator: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
