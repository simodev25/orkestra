"""Platform secrets — API keys and sensitive configuration."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampMixin
from app.core.database import Base


class PlatformSecret(Base, TimestampMixin):
    __tablename__ = "platform_secrets"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g., "OPENAI_API_KEY"
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
