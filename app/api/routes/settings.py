"""Settings API routes -- policy profiles, budget profiles."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.settings import (
    PolicyProfileCreate, PolicyProfileOut,
    BudgetProfileCreate, BudgetProfileOut,
)
from app.services import settings_service

router = APIRouter()


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
