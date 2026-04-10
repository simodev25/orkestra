"""Version history for MCP definitions."""

from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import new_id


class MCPDefinitionHistory(Base):
    """Snapshot of an MCPDefinition at a previous version."""
    __tablename__ = "mcp_definition_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("mcph_"))
    mcp_id: Mapped[str] = mapped_column(String(100), ForeignKey("mcp_definitions.id", ondelete="CASCADE"), index=True)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[str] = mapped_column(String(20))
    replaced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
