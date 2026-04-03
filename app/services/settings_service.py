"""Settings service -- policy profiles, budget profiles, platform settings."""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import PolicyProfile, BudgetProfile
from app.services.event_service import emit_event

logger = logging.getLogger(__name__)


# ---- Policy Profiles ----

async def create_policy_profile(
    db: AsyncSession, name: str, description: str | None = None,
    rules: dict | None = None, is_default: bool = False,
) -> PolicyProfile:
    if is_default:
        # Unset existing defaults
        stmt = select(PolicyProfile).where(PolicyProfile.is_default == True)  # noqa: E712
        result = await db.execute(stmt)
        for existing in result.scalars().all():
            existing.is_default = False

    profile = PolicyProfile(name=name, description=description, rules=rules or {}, is_default=is_default)
    db.add(profile)
    await db.flush()
    await emit_event(db, "settings.policy_created", "admin", "settings_service",
                     payload={"profile_id": profile.id})
    return profile


async def update_policy_profile(db: AsyncSession, profile_id: str, **kwargs) -> PolicyProfile:
    profile = await db.get(PolicyProfile, profile_id)
    if not profile:
        raise ValueError(f"Policy profile {profile_id} not found")

    if kwargs.get("is_default"):
        stmt = select(PolicyProfile).where(
            PolicyProfile.is_default == True, PolicyProfile.id != profile_id  # noqa: E712
        )
        result = await db.execute(stmt)
        for existing in result.scalars().all():
            existing.is_default = False

    for key, value in kwargs.items():
        if value is not None and hasattr(profile, key):
            setattr(profile, key, value)
    await db.flush()
    return profile


async def list_policy_profiles(db: AsyncSession) -> list[PolicyProfile]:
    stmt = select(PolicyProfile).order_by(PolicyProfile.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_policy_profile(db: AsyncSession, profile_id: str) -> PolicyProfile | None:
    return await db.get(PolicyProfile, profile_id)


# ---- Budget Profiles ----

async def create_budget_profile(
    db: AsyncSession, name: str, max_run_cost: float | None = None,
    max_agent_cost: float | None = None, max_mcp_cost: float | None = None,
    soft_limit: float | None = None, hard_limit: float | None = None,
    is_default: bool = False,
) -> BudgetProfile:
    if is_default:
        stmt = select(BudgetProfile).where(BudgetProfile.is_default == True)  # noqa: E712
        result = await db.execute(stmt)
        for existing in result.scalars().all():
            existing.is_default = False

    profile = BudgetProfile(
        name=name, max_run_cost=max_run_cost, max_agent_cost=max_agent_cost,
        max_mcp_cost=max_mcp_cost, soft_limit=soft_limit, hard_limit=hard_limit,
        is_default=is_default,
    )
    db.add(profile)
    await db.flush()
    await emit_event(db, "settings.budget_created", "admin", "settings_service",
                     payload={"profile_id": profile.id})
    return profile


async def update_budget_profile(db: AsyncSession, profile_id: str, **kwargs) -> BudgetProfile:
    profile = await db.get(BudgetProfile, profile_id)
    if not profile:
        raise ValueError(f"Budget profile {profile_id} not found")

    if kwargs.get("is_default"):
        stmt = select(BudgetProfile).where(
            BudgetProfile.is_default == True, BudgetProfile.id != profile_id  # noqa: E712
        )
        result = await db.execute(stmt)
        for existing in result.scalars().all():
            existing.is_default = False

    for key, value in kwargs.items():
        if value is not None and hasattr(profile, key):
            setattr(profile, key, value)
    await db.flush()
    return profile


async def list_budget_profiles(db: AsyncSession) -> list[BudgetProfile]:
    stmt = select(BudgetProfile).order_by(BudgetProfile.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_budget_profile(db: AsyncSession, profile_id: str) -> BudgetProfile | None:
    return await db.get(BudgetProfile, profile_id)
