"""Obot MCP catalog integration + local Orkestra governance bindings."""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.mcp_catalog import OrkestraMCPBinding
from app.schemas.mcp_catalog import (
    CatalogImportResult,
    CatalogMcpDetailsViewModel,
    CatalogMcpViewModel,
    CatalogSyncResult,
    McpCatalogStats,
    ObotServerDetails,
    OrkestraBindingUpdate,
    OrkestraMcpBinding,
)


_OBOT_LIST_ENDPOINTS = ("/api/all-mcps/servers", "/api/mcp-servers")
_OBOT_DETAIL_ENDPOINTS = (
    "/api/all-mcps/servers/{id}",
    "/api/mcp-servers/{id}",
)


def _dedupe(values: list[str] | None) -> list[str]:
    if not values:
        return []
    seen = set()
    out: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _metadata_value(metadata: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata:
            return metadata[key]
    return None


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _map_deployment_to_health(deployment_status: str | None) -> str | None:
    if not deployment_status:
        return None
    status = deployment_status.strip().lower()
    if status == "ready":
        return "healthy"
    if status in {"progressing", "pending"}:
        return "warning"
    if status in {"failed", "error"}:
        return "failing"
    return None


def _map_deployment_to_state(deployment_status: str | None) -> str:
    if not deployment_status:
        return "active"
    status = deployment_status.strip().lower()
    if status == "ready":
        return "active"
    if status in {"failed", "error"}:
        return "degraded"
    if status in {"progressing", "pending"}:
        return "degraded"
    return "active"


def _extract_servers_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("items", "servers", "data", "results"):
        raw_items = payload.get(key)
        if isinstance(raw_items, list):
            return [item for item in raw_items if isinstance(item, dict)]

    return []


def _normalize_obot_payload(raw: dict[str, Any]) -> ObotServerDetails:
    manifest = raw.get("manifest") if isinstance(raw.get("manifest"), dict) else {}
    raw_metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    manifest_metadata = (
        manifest.get("metadata") if isinstance(manifest.get("metadata"), dict) else {}
    )
    combined_metadata: dict[str, Any] = {
        **manifest_metadata,
        **raw_metadata,
    }

    deployment_status = raw.get("deploymentStatus")
    derived_health = _map_deployment_to_health(
        deployment_status if isinstance(deployment_status, str) else None
    )
    derived_state = _map_deployment_to_state(
        deployment_status if isinstance(deployment_status, str) else None
    )

    links = raw.get("links") if isinstance(raw.get("links"), dict) else {}
    obot_url = (
        raw.get("obot_url")
        or raw.get("view_url")
        or links.get("self")
        or links.get("ui")
        or links.get("view")
    )

    description = raw.get("description") or manifest.get("description")
    purpose = (
        raw.get("purpose")
        or manifest.get("shortDescription")
        or description
        or "No purpose documented"
    )

    return ObotServerDetails(
        id=str(raw.get("id") or raw.get("server_id") or raw.get("name") or ""),
        name=str(
            raw.get("name")
            or raw.get("server_name")
            or raw.get("alias")
            or manifest.get("name")
            or raw.get("id")
            or "Unnamed MCP"
        ),
        purpose=str(purpose),
        description=description,
        effect_type=str(
            raw.get("effect_type")
            or _metadata_value(combined_metadata, "effect_type", "effectType")
            or "read"
        ),
        criticality=str(raw.get("criticality") or _metadata_value(combined_metadata, "criticality") or "medium"),
        approval_required=_as_bool(
            raw.get("approval_required")
            if "approval_required" in raw
            else _metadata_value(combined_metadata, "approval_required", "approvalRequired"),
            False,
        ),
        state=str(raw.get("state") or raw.get("status") or derived_state),
        health_status=raw.get("health_status") or derived_health,
        version=raw.get("version") or _metadata_value(combined_metadata, "version"),
        obot_url=obot_url,
        metadata=combined_metadata,
        usage_last_24h=raw.get("usage_last_24h"),
        incidents_last_7d=raw.get("incidents_last_7d"),
        health_note=raw.get("health_note"),
    )


_MOCK_OBOT_SERVERS: list[ObotServerDetails] = [
    ObotServerDetails(
        id="datagouv_search_mcp",
        name="Data.gouv Search MCP",
        purpose="Search datasets and public resources on data.gouv.fr",
        description="Open-data search capability for French public datasets.",
        effect_type="search",
        criticality="low",
        approval_required=False,
        state="active",
        health_status="healthy",
        version="1.3.0",
        obot_url="https://obot.local/servers/datagouv_search_mcp",
        metadata={"provider": "Obot", "region": "eu-west", "audit_enabled": True},
        usage_last_24h=284,
        incidents_last_7d=0,
    ),
    ObotServerDetails(
        id="insee_sirene_lookup_mcp",
        name="INSEE SIRENE Lookup MCP",
        purpose="Lookup legal and administrative company data from INSEE SIRENE",
        description="Company legal identity retrieval for French organizations.",
        effect_type="read",
        criticality="medium",
        approval_required=False,
        state="active",
        health_status="healthy",
        version="2.1.1",
        obot_url="https://obot.local/servers/insee_sirene_lookup_mcp",
        metadata={"provider": "Obot", "region": "eu-west", "audit_enabled": True},
        usage_last_24h=351,
        incidents_last_7d=1,
    ),
    ObotServerDetails(
        id="service_public_company_lookup_mcp",
        name="Service Public Company Lookup MCP",
        purpose="Fetch regulatory and administrative info from service-public APIs",
        description="Regulatory lookup for French legal entities.",
        effect_type="read",
        criticality="medium",
        approval_required=False,
        state="degraded",
        health_status="warning",
        version="1.0.4",
        obot_url="https://obot.local/servers/service_public_company_lookup_mcp",
        metadata={"provider": "Obot", "region": "eu-west", "audit_enabled": True},
        usage_last_24h=98,
        incidents_last_7d=3,
        health_note="Intermittent timeout spikes on weekdays.",
    ),
    ObotServerDetails(
        id="bodacc_events_adapter",
        name="BODACC Events Adapter",
        purpose="Retrieve legal events and publications from BODACC",
        description="Legal events stream for insolvency and corporate status monitoring.",
        effect_type="search",
        criticality="high",
        approval_required=True,
        state="active",
        health_status="healthy",
        version="1.2.2",
        obot_url="https://obot.local/servers/bodacc_events_adapter",
        metadata={"provider": "Obot", "region": "eu-west", "audit_enabled": True},
        usage_last_24h=142,
        incidents_last_7d=0,
    ),
    ObotServerDetails(
        id="boamp_search_adapter",
        name="BOAMP Search Adapter",
        purpose="Search French procurement opportunities and awards",
        description="Procurement intelligence capability.",
        effect_type="search",
        criticality="medium",
        approval_required=False,
        state="active",
        health_status="healthy",
        version="1.1.0",
        obot_url="https://obot.local/servers/boamp_search_adapter",
        metadata={"provider": "Obot", "region": "eu-west", "audit_enabled": False},
        usage_last_24h=77,
        incidents_last_7d=0,
    ),
    ObotServerDetails(
        id="web_search_mcp",
        name="Web Search MCP",
        purpose="General purpose web search for broad evidence collection",
        description="Fallback web search capability for low-trust open web data.",
        effect_type="search",
        criticality="low",
        approval_required=False,
        state="disabled",
        health_status="failing",
        version="2.0.0",
        obot_url="https://obot.local/servers/web_search_mcp",
        metadata={"provider": "Obot", "region": "eu-west", "audit_enabled": False},
        usage_last_24h=0,
        incidents_last_7d=6,
        health_note="Disabled by Obot due to upstream provider quota exhaustion.",
    ),
]


def _compute_orkestra_state(binding: OrkestraMcpBinding) -> str:
    if binding.hidden_from_catalog:
        return "hidden"
    if not binding.enabled_in_orkestra:
        return "disabled"
    if binding.allowed_agent_families or binding.allowed_workflows:
        return "restricted"
    return "enabled"


def _to_binding_schema(binding: OrkestraMCPBinding) -> OrkestraMcpBinding:
    return OrkestraMcpBinding(
        obot_server_id=binding.obot_server_id,
        obot_server_name=binding.obot_server_name,
        enabled_in_orkestra=binding.enabled_in_orkestra,
        hidden_from_catalog=binding.hidden_from_catalog,
        hidden_from_ai_generator=binding.hidden_from_ai_generator,
        allowed_agent_families=_dedupe(binding.allowed_agent_families),
        allowed_workflows=_dedupe(binding.allowed_workflows),
        business_domain=binding.business_domain,
        risk_level_override=binding.risk_level_override,
        preferred_use_cases=_dedupe(binding.preferred_use_cases),
        notes=binding.notes,
        created_at=binding.created_at,
        updated_at=binding.updated_at,
    )


def _default_binding_for(server: ObotServerDetails) -> OrkestraMcpBinding:
    return OrkestraMcpBinding(
        obot_server_id=server.id,
        obot_server_name=server.name,
        enabled_in_orkestra=False,
        hidden_from_catalog=False,
        hidden_from_ai_generator=False,
        allowed_agent_families=[],
        allowed_workflows=[],
        business_domain=None,
        risk_level_override=None,
        preferred_use_cases=[],
        notes=None,
        created_at=None,
        updated_at=None,
    )


async def _fetch_obot_servers_via_api() -> list[ObotServerDetails]:
    settings = get_settings()
    base_url = settings.OBOT_BASE_URL.rstrip("/")
    if not base_url:
        return []

    headers: dict[str, str] = {}
    if settings.OBOT_API_KEY:
        headers["Authorization"] = f"Bearer {settings.OBOT_API_KEY}"

    async with httpx.AsyncClient(timeout=settings.OBOT_TIMEOUT_SECONDS) as client:
        last_error: Exception | None = None
        at_least_one_endpoint_ok = False
        best_servers: list[ObotServerDetails] = []

        for endpoint in _OBOT_LIST_ENDPOINTS:
            url = f"{base_url}{endpoint}"
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                at_least_one_endpoint_ok = True
                payload = resp.json()
                servers_raw = _extract_servers_payload(payload)
                servers: list[ObotServerDetails] = []
                for raw in servers_raw:
                    normalized = _normalize_obot_payload(raw)
                    if normalized.id:
                        if not normalized.obot_url:
                            normalized.obot_url = f"{base_url}{endpoint}/{normalized.id}"
                        servers.append(normalized)

                # Some Obot installations expose richer data on one endpoint
                # and empty lists on the other. Keep the non-empty/bigger set.
                if len(servers) > len(best_servers):
                    best_servers = servers
            except Exception as exc:  # pragma: no cover - exercised in integration
                last_error = exc

        if at_least_one_endpoint_ok:
            return best_servers
        if last_error is not None:
            raise last_error

    raise ValueError("No compatible Obot MCP list endpoint found")


async def _fetch_obot_server_by_id_via_api(obot_server_id: str) -> ObotServerDetails | None:
    settings = get_settings()
    base_url = settings.OBOT_BASE_URL.rstrip("/")
    if not base_url:
        return None

    headers: dict[str, str] = {}
    if settings.OBOT_API_KEY:
        headers["Authorization"] = f"Bearer {settings.OBOT_API_KEY}"

    async with httpx.AsyncClient(timeout=settings.OBOT_TIMEOUT_SECONDS) as client:
        for endpoint in _OBOT_DETAIL_ENDPOINTS:
            url = f"{base_url}{endpoint.format(id=obot_server_id)}"
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, dict):
                continue
            normalized = _normalize_obot_payload(payload)
            if not normalized.obot_url:
                normalized.obot_url = url
            if normalized.id:
                return normalized
    return None


async def fetch_obot_servers() -> tuple[list[ObotServerDetails], str]:
    settings = get_settings()

    if settings.OBOT_BASE_URL and not settings.OBOT_USE_MOCK:
        try:
            return await _fetch_obot_servers_via_api(), "obot"
        except Exception:
            if not settings.OBOT_FALLBACK_TO_MOCK:
                raise

    return _MOCK_OBOT_SERVERS, "mock"


async def fetch_obot_server_by_id(obot_server_id: str) -> tuple[ObotServerDetails | None, str]:
    settings = get_settings()

    if settings.OBOT_BASE_URL and not settings.OBOT_USE_MOCK:
        try:
            server = await _fetch_obot_server_by_id_via_api(obot_server_id)
            if server is not None:
                return server, "obot"

            servers = await _fetch_obot_servers_via_api()
            for item in servers:
                if item.id == obot_server_id:
                    return item, "obot"
            return None, "obot"
        except Exception:
            if not settings.OBOT_FALLBACK_TO_MOCK:
                raise

    for server in _MOCK_OBOT_SERVERS:
        if server.id == obot_server_id:
            return server, "mock"
    return None, "mock"


def map_obot_server_to_catalog_item(
    server: ObotServerDetails,
    binding: OrkestraMcpBinding,
    *,
    is_imported: bool,
) -> CatalogMcpViewModel:
    obot_state = server.state
    return CatalogMcpViewModel(
        obot_server=server,
        orkestra_binding=binding,
        obot_state=obot_state,
        orkestra_state=_compute_orkestra_state(binding),
        is_imported_in_orkestra=is_imported,
    )


async def _get_bindings_map(db: AsyncSession) -> dict[str, OrkestraMCPBinding]:
    rows = await db.execute(select(OrkestraMCPBinding))
    return {binding.obot_server_id: binding for binding in rows.scalars().all()}


async def sync_obot_catalog(db: AsyncSession) -> CatalogSyncResult:
    servers, source = await fetch_obot_servers()
    bindings = await _get_bindings_map(db)

    updated = 0
    for server in servers:
        existing = bindings.get(server.id)
        if existing is None:
            continue
        if existing.obot_server_name != server.name:
            existing.obot_server_name = server.name
            updated += 1

    await db.flush()

    return CatalogSyncResult(
        total_obot_servers=len(servers),
        existing_bindings_updated=updated,
        missing_bindings=sum(1 for server in servers if server.id not in bindings),
        source=source,
    )


async def import_from_obot(
    db: AsyncSession,
    obot_server_ids: list[str] | None = None,
) -> CatalogImportResult:
    servers, _ = await fetch_obot_servers()
    if obot_server_ids:
        wanted = set(obot_server_ids)
        selected = [server for server in servers if server.id in wanted]
    else:
        selected = servers

    bindings = await _get_bindings_map(db)
    imported_count = 0
    updated_count = 0

    for server in selected:
        existing = bindings.get(server.id)
        if existing is None:
            db.add(
                OrkestraMCPBinding(
                    obot_server_id=server.id,
                    obot_server_name=server.name,
                    enabled_in_orkestra=False,
                    hidden_from_catalog=False,
                    hidden_from_ai_generator=False,
                    allowed_agent_families=[],
                    allowed_workflows=[],
                    preferred_use_cases=[],
                )
            )
            imported_count += 1
            continue
        if existing.obot_server_name != server.name:
            existing.obot_server_name = server.name
            updated_count += 1

    await db.flush()
    return CatalogImportResult(
        imported_count=imported_count,
        updated_count=updated_count,
        total_selected=len(selected),
    )


async def _ensure_binding(db: AsyncSession, obot_server_id: str) -> OrkestraMCPBinding:
    existing = await db.get(OrkestraMCPBinding, obot_server_id)
    if existing:
        return existing

    server, _ = await fetch_obot_server_by_id(obot_server_id)
    if not server:
        raise ValueError(f"Obot server {obot_server_id} not found")

    binding = OrkestraMCPBinding(
        obot_server_id=server.id,
        obot_server_name=server.name,
        enabled_in_orkestra=False,
        hidden_from_catalog=False,
        hidden_from_ai_generator=False,
        allowed_agent_families=[],
        allowed_workflows=[],
        preferred_use_cases=[],
    )
    db.add(binding)
    await db.flush()
    return binding


async def update_orkestra_binding(
    db: AsyncSession,
    obot_server_id: str,
    payload: OrkestraBindingUpdate,
) -> OrkestraMcpBinding:
    binding = await _ensure_binding(db, obot_server_id)
    updates = payload.model_dump(exclude_none=True)

    list_fields = {"allowed_agent_families", "allowed_workflows", "preferred_use_cases"}
    for key, value in updates.items():
        if key in list_fields and isinstance(value, list):
            setattr(binding, key, _dedupe(value))
        else:
            setattr(binding, key, value)

    await db.flush()
    return _to_binding_schema(binding)


async def enable_in_orkestra(db: AsyncSession, obot_server_id: str) -> OrkestraMcpBinding:
    binding = await _ensure_binding(db, obot_server_id)
    binding.enabled_in_orkestra = True
    await db.flush()
    return _to_binding_schema(binding)


async def disable_in_orkestra(db: AsyncSession, obot_server_id: str) -> OrkestraMcpBinding:
    binding = await _ensure_binding(db, obot_server_id)
    binding.enabled_in_orkestra = False
    await db.flush()
    return _to_binding_schema(binding)


async def bind_to_workflow(db: AsyncSession, obot_server_id: str, workflow_id: str) -> OrkestraMcpBinding:
    binding = await _ensure_binding(db, obot_server_id)
    workflows = _dedupe([*(binding.allowed_workflows or []), workflow_id])
    binding.allowed_workflows = workflows
    await db.flush()
    return _to_binding_schema(binding)


async def bind_to_agent_family(
    db: AsyncSession,
    obot_server_id: str,
    agent_family: str,
) -> OrkestraMcpBinding:
    binding = await _ensure_binding(db, obot_server_id)
    families = _dedupe([*(binding.allowed_agent_families or []), agent_family])
    binding.allowed_agent_families = families
    await db.flush()
    return _to_binding_schema(binding)


async def list_catalog_items(
    db: AsyncSession,
    *,
    search: str | None = None,
    obot_status: str | None = None,
    orkestra_status: str | None = None,
    criticality: str | None = None,
    effect_type: str | None = None,
    approval_required: bool | None = None,
    allowed_workflow: str | None = None,
    allowed_agent_family: str | None = None,
    hidden_from_ai_generator: bool | None = None,
) -> list[CatalogMcpViewModel]:
    servers, _ = await fetch_obot_servers()
    bindings = await _get_bindings_map(db)

    out: list[CatalogMcpViewModel] = []
    for server in servers:
        existing = bindings.get(server.id)
        binding = _to_binding_schema(existing) if existing else _default_binding_for(server)
        view = map_obot_server_to_catalog_item(server, binding, is_imported=existing is not None)

        if search:
            q = search.lower()
            if q not in server.name.lower() and q not in server.id.lower() and q not in server.purpose.lower():
                continue
        if obot_status and obot_status != "all" and view.obot_state != obot_status:
            continue
        if orkestra_status and orkestra_status != "all" and view.orkestra_state != orkestra_status:
            continue
        if criticality and criticality != "all" and server.criticality != criticality:
            continue
        if effect_type and effect_type != "all" and server.effect_type != effect_type:
            continue
        if approval_required is not None and server.approval_required != approval_required:
            continue
        if allowed_workflow and allowed_workflow not in binding.allowed_workflows:
            continue
        if allowed_agent_family and allowed_agent_family not in binding.allowed_agent_families:
            continue
        if hidden_from_ai_generator is not None and binding.hidden_from_ai_generator != hidden_from_ai_generator:
            continue

        out.append(view)

    out.sort(key=lambda item: item.obot_server.name.lower())
    return out


async def get_catalog_item(db: AsyncSession, obot_server_id: str) -> CatalogMcpDetailsViewModel:
    server, _ = await fetch_obot_server_by_id(obot_server_id)
    if not server:
        raise ValueError(f"Obot server {obot_server_id} not found")

    binding_db = await db.get(OrkestraMCPBinding, obot_server_id)
    binding = _to_binding_schema(binding_db) if binding_db else _default_binding_for(server)

    return CatalogMcpDetailsViewModel(
        obot_server=server,
        orkestra_binding=binding,
        obot_state=server.state,
        orkestra_state=_compute_orkestra_state(binding),
        is_imported_in_orkestra=binding_db is not None,
    )


async def get_catalog_stats(db: AsyncSession) -> McpCatalogStats:
    items = await list_catalog_items(db)
    return McpCatalogStats(
        obot_total=len(items),
        obot_active=sum(1 for item in items if item.obot_state == "active"),
        obot_degraded=sum(1 for item in items if item.obot_state == "degraded"),
        obot_disabled=sum(1 for item in items if item.obot_state == "disabled"),
        orkestra_enabled=sum(1 for item in items if item.orkestra_state == "enabled"),
        orkestra_disabled=sum(1 for item in items if item.orkestra_state == "disabled"),
        orkestra_restricted=sum(1 for item in items if item.orkestra_state == "restricted"),
        orkestra_hidden=sum(1 for item in items if item.orkestra_state == "hidden"),
        critical=sum(1 for item in items if item.obot_server.criticality == "high"),
        approval_required=sum(1 for item in items if item.obot_server.approval_required),
        hidden_from_ai_generator=sum(
            1 for item in items if item.orkestra_binding.hidden_from_ai_generator
        ),
    )
