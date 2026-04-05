"""Settings API routes -- policy profiles, budget profiles, platform secrets."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.settings import (
    PolicyProfileCreate, PolicyProfileOut,
    BudgetProfileCreate, BudgetProfileOut,
)
from app.services import settings_service

router = APIRouter()


class SecretUpsert(PydanticBaseModel):
    value: str
    description: str = ""


# ---- Policy Profiles ----

@router.post("/policy-profiles", response_model=PolicyProfileOut, status_code=201)
async def create_policy(data: PolicyProfileCreate, db: AsyncSession = Depends(get_db)):
    return await settings_service.create_policy_profile(
        db, data.name, data.description, data.rules, data.is_default)


@router.get("/policy-profiles", response_model=list[PolicyProfileOut])
async def list_policies(db: AsyncSession = Depends(get_db)):
    return await settings_service.list_policy_profiles(db)


@router.get("/policy-profiles/{profile_id}", response_model=PolicyProfileOut)
async def get_policy(profile_id: str, db: AsyncSession = Depends(get_db)):
    p = await settings_service.get_policy_profile(db, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Policy profile not found")
    return p


# ---- Budget Profiles ----

@router.post("/budget-profiles", response_model=BudgetProfileOut, status_code=201)
async def create_budget(data: BudgetProfileCreate, db: AsyncSession = Depends(get_db)):
    return await settings_service.create_budget_profile(
        db, data.name, data.max_run_cost, data.max_agent_cost, data.max_mcp_cost,
        data.soft_limit, data.hard_limit, data.is_default)


@router.get("/budget-profiles", response_model=list[BudgetProfileOut])
async def list_budgets(db: AsyncSession = Depends(get_db)):
    return await settings_service.list_budget_profiles(db)


@router.get("/budget-profiles/{profile_id}", response_model=BudgetProfileOut)
async def get_budget(profile_id: str, db: AsyncSession = Depends(get_db)):
    b = await settings_service.get_budget_profile(db, profile_id)
    if not b:
        raise HTTPException(status_code=404, detail="Budget profile not found")
    return b


# ---- Platform Secrets (API Keys) ----

@router.get("/secrets")
async def list_secrets(db: AsyncSession = Depends(get_db)):
    """List all secrets with masked values."""
    from app.models.secret import PlatformSecret
    result = await db.execute(select(PlatformSecret).order_by(PlatformSecret.id))
    secrets = list(result.scalars().all())
    return [
        {
            "id": s.id,
            "value_masked": s.value[:4] + "****" + s.value[-4:] if len(s.value) > 8 else "****",
            "description": s.description,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in secrets
    ]


@router.put("/secrets/{secret_id}")
async def upsert_secret(secret_id: str, data: SecretUpsert, db: AsyncSession = Depends(get_db)):
    """Create or update a secret."""
    from app.models.secret import PlatformSecret

    value = data.value.strip()
    description = data.description.strip()

    if not value:
        raise HTTPException(status_code=400, detail="value is required")

    existing = await db.get(PlatformSecret, secret_id)
    if existing:
        existing.value = value
        if description:
            existing.description = description
    else:
        secret = PlatformSecret(id=secret_id, value=value, description=description or None)
        db.add(secret)

    await db.flush()
    return {"id": secret_id, "status": "saved"}


@router.delete("/secrets/{secret_id}")
async def delete_secret(secret_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a secret."""
    from app.models.secret import PlatformSecret
    existing = await db.get(PlatformSecret, secret_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Secret not found")
    await db.delete(existing)
    await db.flush()
    return {"id": secret_id, "status": "deleted"}
