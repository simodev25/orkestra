"""PolicyProfile and BudgetProfile entities."""

from sqlalchemy import String, Float, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, new_id


class PolicyProfile(BaseModel):
    __tablename__ = "policy_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("pol_"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class BudgetProfile(BaseModel):
    __tablename__ = "budget_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("bud_"))
    name: Mapped[str] = mapped_column(String(255))
    max_run_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_agent_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_mcp_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    soft_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    hard_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
