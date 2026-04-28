"""Settings API routes -- policy profiles, budget profiles, platform secrets."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.database import get_db
from app.core.encryption import encrypt_value
from app.core.rate_limit import limiter
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
@limiter.limit("10/minute")
async def upsert_secret(request: Request, secret_id: str, data: SecretUpsert, db: AsyncSession = Depends(get_db)):
    """Create or update a secret."""
    from app.models.secret import PlatformSecret

    value = data.value.strip()
    description = data.description.strip()

    if not value:
        raise HTTPException(status_code=400, detail="value is required")

    existing = await db.get(PlatformSecret, secret_id)
    if existing:
        existing.value = encrypt_value(value)
        if description:
            existing.description = description
    else:
        secret = PlatformSecret(id=secret_id, value=encrypt_value(value), description=description or None)
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


# ---- Platform Capabilities (global feature toggles) ----

class CapabilityUpsert(PydanticBaseModel):
    value: str  # "true" | "false"


@router.get("/capabilities")
async def list_capabilities(db: AsyncSession = Depends(get_db)):
    """Return all platform capability flags as {key: bool} map."""
    from app.models.platform_capability import PlatformCapability
    result = await db.execute(select(PlatformCapability).order_by(PlatformCapability.key))
    rows = list(result.scalars().all())
    return {r.key: r.value.lower() == "true" for r in rows}


@router.put("/capabilities/{cap_key}")
async def set_capability(cap_key: str, data: CapabilityUpsert, db: AsyncSession = Depends(get_db)):
    """Create or update a capability flag."""
    from app.models.platform_capability import PlatformCapability
    from datetime import datetime, timezone

    normalized = "true" if str(data.value).lower() in ("true", "1", "yes") else "false"
    existing = await db.get(PlatformCapability, cap_key)
    if existing:
        existing.value = normalized
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.add(PlatformCapability(key=cap_key, value=normalized))
    await db.flush()
    return {"key": cap_key, "value": normalized == "true"}


# ---- LLM Configuration ----

_LLM_CONFIG_KEYS = ["LLM_PROVIDER", "OLLAMA_HOST", "OLLAMA_MODEL", "OPENAI_MODEL", "OPENAI_BASE_URL"]

_LLM_DEFAULTS = {
    "LLM_PROVIDER": "ollama",
    "OLLAMA_HOST": "http://localhost:11434",
    "OLLAMA_MODEL": "mistral",
    "OPENAI_MODEL": "gpt-4o-mini",
    "OPENAI_BASE_URL": "https://api.openai.com/v1",
}


class LlmConfigUpdate(PydanticBaseModel):
    provider: str = "ollama"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"


@router.get("/llm-config")
async def get_llm_config(db: AsyncSession = Depends(get_db)):
    """Return current LLM configuration (DB overrides env vars)."""
    from app.models.platform_capability import PlatformCapability
    from app.core.config import get_settings
    result = await db.execute(
        select(PlatformCapability).where(PlatformCapability.key.in_(_LLM_CONFIG_KEYS))
    )
    rows = {r.key: r.value for r in result.scalars().all()}
    settings = get_settings()
    def _get(cap_key: str, env_attr: str) -> str:
        return rows.get(cap_key) or getattr(settings, env_attr, None) or _LLM_DEFAULTS[cap_key]
    return {
        "provider":       _get("LLM_PROVIDER",    "LLM_PROVIDER"),
        "ollama_host":    _get("OLLAMA_HOST",      "OLLAMA_HOST"),
        "ollama_model":   _get("OLLAMA_MODEL",     "OLLAMA_MODEL"),
        "openai_model":   _get("OPENAI_MODEL",     "OPENAI_MODEL"),
        "openai_base_url":_get("OPENAI_BASE_URL",  "OPENAI_BASE_URL"),
    }


@router.put("/llm-config")
async def save_llm_config(data: LlmConfigUpdate, db: AsyncSession = Depends(get_db)):
    """Persist LLM configuration to platform_capabilities."""
    from app.models.platform_capability import PlatformCapability
    from datetime import datetime, timezone
    updates = {
        "LLM_PROVIDER":    data.provider.strip(),
        "OLLAMA_HOST":     data.ollama_host.strip(),
        "OLLAMA_MODEL":    data.ollama_model.strip(),
        "OPENAI_MODEL":    data.openai_model.strip(),
        "OPENAI_BASE_URL": data.openai_base_url.strip(),
    }
    for key, value in updates.items():
        existing = await db.get(PlatformCapability, key)
        if existing:
            existing.value = value
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(PlatformCapability(key=key, value=value))
    await db.flush()
    return {"status": "saved", **{k.lower(): v for k, v in updates.items()}}
