"""Agent factory -- creates AgentScope ReActAgent from Orkestra agent definitions."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import AgentDefinition
from app.llm.provider import get_chat_model, get_formatter, is_agentscope_available, make_ollama_model

logger = logging.getLogger(__name__)

# ── MCP schema patches ────────────────────────────────────────────────────────

_WAYPOINT_SCHEMA = {
    "type": "object",
    "description": (
        "A waypoint for routing. Provide exactly ONE of: "
        "address (plain string), place_id (from search_places), or lat_lng."
    ),
    "properties": {
        "address": {
            "type": "string",
            "description": "Street address or place name, e.g. 'Humberto Delgado Airport, Lisbon'",
        },
        "place_id": {
            "type": "string",
            "description": "Google Maps place ID returned by search_places, e.g. 'ChIJxxx...'",
        },
        "lat_lng": {
            "type": "object",
            "description": "Geographic coordinates",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["latitude", "longitude"],
        },
    },
}


def _patch_mcp_tool_schemas(tools: list) -> None:
    """Fix inputSchema mismatches for known MCP tools.

    Google Maps Grounding Lite declares ``origin``/``destination`` as plain
    strings, but the API expects Waypoint objects.  Patching the schema here
    ensures the LLM generates the correct nested object format.
    """
    for tool in tools:
        if tool.name == "compute_routes":
            props = tool.inputSchema.setdefault("properties", {})
            props["origin"] = _WAYPOINT_SCHEMA
            props["destination"] = _WAYPOINT_SCHEMA
            tool.inputSchema.setdefault("required", ["origin", "destination"])
            logger.info("Patched compute_routes schema: origin/destination → Waypoint objects")


# ── Exception formatting ──────────────────────────────────────────────────────


def _format_mcp_exception(e: Exception) -> str:
    """Unwrap BaseExceptionGroup to extract and display the real inner exceptions.

    AgentScope's HttpStatelessClient wraps downstream errors (HTTP 403, network
    failures, JSON-RPC errors) inside an asyncio TaskGroup ExceptionGroup.
    str(ExceptionGroup) only shows 'unhandled errors in a TaskGroup (N sub-exception)'
    which is opaque. This helper extracts the inner exceptions for clear logging.
    """
    # Python 3.11+ ExceptionGroup / BaseExceptionGroup
    if hasattr(e, "exceptions"):
        parts = []
        for inner in e.exceptions:  # type: ignore[attr-defined]
            parts.append(_format_mcp_exception(inner))
        return f"[{type(e).__name__}] " + " | ".join(parts)
    return f"{type(e).__name__}: {e}"




async def _read_platform_llm_config(db: AsyncSession) -> dict:
    """Read LLM host/api_key from platform_capabilities + platform_secrets tables."""
    try:
        from sqlalchemy import select
        from app.models.platform_capability import PlatformCapability
        from app.models.secret import PlatformSecret
        from app.core.encryption import decrypt_value

        _KEYS = ["LLM_PROVIDER", "OLLAMA_HOST", "OLLAMA_MODEL", "OPENAI_MODEL", "OPENAI_BASE_URL"]
        result = await db.execute(
            select(PlatformCapability).where(PlatformCapability.key.in_(_KEYS))
        )
        rows = {r.key: r.value for r in result.scalars().all()}

        ollama_secret = await db.get(PlatformSecret, "OLLAMA_API_KEY")
        openai_secret = await db.get(PlatformSecret, "OPENAI_API_KEY")

        def _decrypt(secret) -> str | None:
            if secret is None:
                return None
            try:
                return decrypt_value(secret.value)
            except Exception:
                return None

        return {
            "provider":        rows.get("LLM_PROVIDER"),
            "ollama_host":     rows.get("OLLAMA_HOST"),
            "ollama_model":    rows.get("OLLAMA_MODEL"),
            "openai_model":    rows.get("OPENAI_MODEL"),
            "openai_base_url": rows.get("OPENAI_BASE_URL"),
            "ollama_api_key":  _decrypt(ollama_secret),
            "openai_api_key":  _decrypt(openai_secret),
        }
    except Exception as e:
        logger.warning(f"Could not read platform LLM config from DB: {e}")
        return {}


def _get_agent_specific_model(provider: str, model_name: str, platform_cfg: dict | None = None):
    """Create a model instance for a specific provider/model combination.

    ``platform_cfg`` is the dict from _read_platform_llm_config (platform_capabilities + secrets).
    When provided, its host/api_key take precedence over env vars.
    """
    if not is_agentscope_available():
        return None
    cfg = platform_cfg or {}
    try:
        if provider == "ollama":
            from app.core.config import get_settings
            settings = get_settings()
            base_url = cfg.get("ollama_host") or getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
            api_key = cfg.get("ollama_api_key") or getattr(settings, "OLLAMA_API_KEY", None)
            return make_ollama_model(base_url, model_name, api_key)
        elif provider == "openai":
            from agentscope.model import OpenAIChatModel
            from app.core.config import get_settings
            settings = get_settings()
            api_key = cfg.get("openai_api_key") or getattr(settings, "OPENAI_API_KEY", "")
            base_url = cfg.get("openai_base_url") or getattr(settings, "OPENAI_BASE_URL", None) or "https://api.openai.com/v1"
            return OpenAIChatModel(
                model_name=model_name,
                api_key=api_key,
                base_url=base_url,
            )
        return None
    except Exception as e:
        logger.warning(f"Failed to create agent-specific model {provider}/{model_name}: {e}")
        return None


async def _register_orkestra_skills(
    db: AsyncSession,
    agent_def: AgentDefinition,
    toolkit,
) -> None:
    """Register agent skills from skills_content field directly in toolkit.skills."""
    from agentscope.tool._types import AgentSkill

    if not agent_def.skills_content:
        return

    from app.core.config import get_settings
    db_url = get_settings().DATABASE_URL.replace("asyncpg", "postgresql")

    toolkit.skills[agent_def.name] = AgentSkill(
        name=f"{agent_def.name} Skills",
        description=agent_def.skills_content,
        dir=f"{db_url}/agent_definitions/{agent_def.id}/skills_content",
    )
    logger.info(f"Registered skills_content for agent {agent_def.id} from PostgreSQL")


async def resolve_mcp_servers(db: AsyncSession, agent_def: AgentDefinition) -> list[dict]:
    """Resolve MCP server endpoint URLs from the agent's allowed_mcps IDs.

    For each ID in allowed_mcps:
    - Checks that the MCP is enabled in Orkestra (OrkestraMCPBinding.enabled_in_orkestra)
    - Fetches the remoteConfig.url from the Obot catalog
    Returns list of dicts: [{"id": "ms1rwk5g", "name": "...", "url": "https://..."}]
    """
    allowed = agent_def.allowed_mcps or []
    if not allowed:
        return []

    from app.services.obot_catalog_service import fetch_obot_server_by_id
    from app.models.mcp_catalog import OrkestraMCPBinding

    servers = []
    for mcp_id in allowed:
        # 1. Check if enabled in Orkestra
        binding = await db.get(OrkestraMCPBinding, mcp_id)
        if binding and not binding.enabled_in_orkestra:
            logger.info(f"MCP {mcp_id} is disabled in Orkestra — skipping")
            continue

        # 2. Get endpoint URL from Obot catalog
        try:
            server, _ = await fetch_obot_server_by_id(mcp_id)
            if server:
                url = server.mcp_endpoint_url
                if url:
                    servers.append({"id": mcp_id, "name": server.name, "url": url})
                    logger.info(f"MCP {mcp_id} ({server.name}) → {url}")
                else:
                    logger.warning(f"MCP {mcp_id} ({server.name}) has no remoteConfig.url — cannot connect")
            else:
                logger.warning(f"MCP {mcp_id} not found in Obot catalog")
        except Exception as exc:
            logger.warning(f"Failed to resolve MCP {mcp_id} from Obot: {exc}")

    return servers


async def _is_code_execution_platform_enabled(db: AsyncSession) -> bool:
    """Return True if the platform-wide code_execution_enabled capability is set."""
    try:
        from app.models.platform_capability import PlatformCapability
        cap = await db.get(PlatformCapability, "code_execution_enabled")
        if cap is None:
            return False  # not seeded yet → default OFF
        return cap.value.lower() == "true"
    except Exception as exc:
        logger.warning(f"Could not read platform capability code_execution_enabled: {exc}")
        return False


async def create_agentscope_agent(
    agent_def: AgentDefinition,
    db: AsyncSession,
    tools_to_register: list | None = None,
    max_iters: int = 5,
    fallback_model=None,
    fallback_formatter=None,
    test_run_id: str | None = None,
):
    """Create an AgentScope ReActAgent from an Orkestra AgentDefinition.

    Connects to MCP servers declared in allowed_mcps and registers their tools.
    Returns None if AgentScope or LLM is not available.

    fallback_model / fallback_formatter: used when the agent definition does not
    specify llm_provider/llm_model. Callers in the test lab pass the test lab
    config model so the target agent uses the same model as the orchestrator.
    """
    if not is_agentscope_available():
        logger.info(f"AgentScope not available, cannot create agent {agent_def.id}")
        return None

    # Read platform LLM config (host, api_key) from DB — takes precedence over env vars
    platform_cfg = await _read_platform_llm_config(db)

    if agent_def.llm_provider and agent_def.llm_model:
        model = _get_agent_specific_model(agent_def.llm_provider, agent_def.llm_model, platform_cfg)
        logger.info("[AGENT-MODEL] agent=%s path=agent_specific provider=%s model=%s", agent_def.id, agent_def.llm_provider, agent_def.llm_model)
    elif fallback_model is not None:
        model = fallback_model
        try:
            _mname = getattr(model, "model_name", "?")
            _host = str(model.client._client._base_url) if hasattr(model, "client") else "?"
        except Exception:
            _mname = str(type(model))
            _host = "?"
        logger.info("[AGENT-MODEL] agent=%s path=fallback model_type=%s host=%s model=%s", agent_def.id, type(model).__name__, _host, _mname)
    else:
        model = get_chat_model(config=platform_cfg)
        logger.info("[AGENT-MODEL] agent=%s path=platform_cfg ollama_host=%s ollama_api_key=%s", agent_def.id, platform_cfg.get("ollama_host"), "SET" if platform_cfg.get("ollama_api_key") else "NOT_SET")
    if model is None:
        logger.info(f"LLM not available, cannot create agent {agent_def.id}")
        return None

    formatter = fallback_formatter if fallback_formatter is not None else get_formatter()
    if formatter is None:
        return None

    try:
        from agentscope.agent import ReActAgent
        from agentscope.tool import Toolkit
        from agentscope.memory import InMemoryMemory
        from app.services.prompt_builder import build_agent_prompt

        toolkit = Toolkit()

        # Build the allowlist set once for deterministic enforcement
        allowed = set(agent_def.allowed_mcps or [])

        # Register execute_python_code if the agent has opted in AND the
        # platform-level code_execution_enabled flag is true.
        if getattr(agent_def, "allow_code_execution", False):
            platform_enabled = await _is_code_execution_platform_enabled(db)
            if platform_enabled:
                from app.services.sandbox_tool import get_code_execution_tool
                code_tool = get_code_execution_tool()
                if code_tool is not None:
                    toolkit.register_tool_function(code_tool)
                    logger.info(f"Agent {agent_def.id}: code execution enabled")
                else:
                    logger.warning(f"Agent {agent_def.id}: code execution opted in but no tool available")
            else:
                logger.info(
                    f"Agent {agent_def.id}: allow_code_execution=True but platform toggle is OFF — skipping"
                )

        # Register agentscope built-in tools selected for this agent
        # Each tool gets its appropriate sandbox image (BaseSandbox / FilesystemSandbox)
        # with automatic fallback to the bare function when Docker DinD is unavailable.
        builtin_tools = getattr(agent_def, "allowed_builtin_tools", None) or []
        if builtin_tools:
            from app.services.sandbox_tool import get_sandboxed_tool
            for tool_name in builtin_tools:
                tool_fn = get_sandboxed_tool(tool_name)
                if tool_fn is not None:
                    toolkit.register_tool_function(tool_fn)
                    logger.info(f"Agent {agent_def.id}: registered built-in tool '{tool_name}'")
                else:
                    logger.warning(f"Agent {agent_def.id}: built-in tool '{tool_name}' not available")

        # Register local tool functions, enforcing the MCP allowlist
        if tools_to_register:
            from app.services.mcp_tool_registry import get_mcp_id_for_tool
            for tool_func in tools_to_register:
                mcp_id = get_mcp_id_for_tool(tool_func)
                if allowed and mcp_id and mcp_id not in allowed:
                    logger.warning(f"Skipping local tool '{getattr(tool_func, '__name__', tool_func)}' from MCP {mcp_id}: not in agent's allowed_mcps")
                    continue
                toolkit.register_tool_function(tool_func)

        # Register Orkestra skills via AgentScope register_agent_skill
        await _register_orkestra_skills(db, agent_def, toolkit)

        # Connect to remote MCP servers and register their tools, enforcing the MCP allowlist
        mcp_servers = await resolve_mcp_servers(db, agent_def)
        connected_mcps = []
        for srv in mcp_servers:
            mcp_id = srv["id"]
            if allowed and mcp_id not in allowed:
                logger.warning(f"Skipping MCP {mcp_id}: not in agent's allowed_mcps")
                continue
            if not srv.get("url"):
                logger.warning(f"MCP {mcp_id} has no URL, skipping")
                continue
            try:
                from agentscope.mcp import HttpStatelessClient
                from app.core.config import get_settings as _get_settings
                _settings = _get_settings()
                _mcp_headers: dict[str, str] = {}
                if _settings.OBOT_API_KEY:
                    _mcp_headers["Authorization"] = f"Bearer {_settings.OBOT_API_KEY}"
                mcp_client = HttpStatelessClient(
                    name=mcp_id,
                    transport="streamable_http",
                    url=srv["url"],
                    timeout=30,
                    headers=_mcp_headers,
                )
                # List available tools and register them
                mcp_tools = await mcp_client.list_tools()
                logger.info(f"MCP {mcp_id} ({srv['url']}): {len(mcp_tools)} tools found")

                # Pre-flight effect enforcement: classify each tool and record
                # denied invocations for tools whose ALL effects are forbidden.
                # Only runs when the agent has forbidden_effects AND a run_id exists.
                if agent_def.forbidden_effects and test_run_id and db:
                    from app.services.effect_classifier import get_classifier
                    from app.models.invocation import MCPInvocation
                    from datetime import datetime, timezone
                    from app.services.event_service import emit_event
                    _eff_classifier = get_classifier()
                    _forbidden_set = set(agent_def.forbidden_effects)
                    _allowed_tools = []
                    for _tool in mcp_tools:
                        _effects = await _eff_classifier.classify(_tool.name, {})
                        _blocked = [e for e in _effects if e in _forbidden_set]
                        if _blocked and set(_effects) <= _forbidden_set:
                            # ALL effects are forbidden — skip tool registration
                            logger.warning(
                                "[EffectEnforcement] Pre-flight: agent=%s tool=%s blocked effects=%s",
                                agent_def.id, _tool.name, _blocked,
                            )
                            _inv = MCPInvocation(
                                run_id=test_run_id,
                                mcp_id=mcp_id,
                                calling_agent_id=agent_def.id,
                                effect_type=",".join(sorted(_blocked)),
                                status="denied",
                                approval_required=False,
                                started_at=datetime.now(timezone.utc),
                                ended_at=datetime.now(timezone.utc),
                            )
                            db.add(_inv)
                            await db.flush()
                            await emit_event(
                                db, "mcp.denied", "runtime", "agent_factory",
                                run_id=test_run_id,
                                payload={
                                    "mcp_id": mcp_id,
                                    "agent_id": agent_def.id,
                                    "reason": "forbidden_effect",
                                    "tool": _tool.name,
                                    "effects": _blocked,
                                },
                            )
                        else:
                            _allowed_tools.append(_tool)
                    mcp_tools = _allowed_tools

                # Patch known schema mismatches — some MCP servers declare
                # complex object parameters as plain strings in their inputSchema,
                # causing the LLM to generate strings where objects are required.
                _patch_mcp_tool_schemas(mcp_tools)
                if mcp_tools:
                    await toolkit.register_mcp_client(
                        mcp_client=mcp_client,
                        group_name="basic",
                        namesake_strategy="rename",
                    )
                    connected_mcps.append({
                        "id": mcp_id,
                        "url": srv["url"],
                        "tools": [t.name for t in mcp_tools],
                    })
                    # Probe: verify that tool execution is actually reachable.
                    # list_tools() only checks the /tools/list endpoint; the
                    # downstream API key (e.g. Google Maps X-GOOG-API-KEY) is
                    # only validated on the first real tool call.  We call the
                    # first tool with empty arguments — it will fail with
                    # invalid-argument, but an API-key error appears here too
                    # and is much easier to diagnose than a silent TaskGroup
                    # failure inside the agent loop.
                    try:
                        probe_fn = await mcp_client.get_callable_function(
                            mcp_tools[0].name, wrap_tool_result=False
                        )
                        await probe_fn()
                    except BaseException as probe_err:  # noqa: BLE001
                        real_err = _format_mcp_exception(probe_err)
                        # A JSON-RPC "invalid params" error is fine (tool works).
                        # A 403/blocked message means the API key is missing.
                        if "invalid" in real_err.lower() or "argument" in real_err.lower() or "param" in real_err.lower():
                            logger.debug(f"MCP {mcp_id} probe OK (expected param error): {real_err}")
                        else:
                            logger.warning(
                                f"MCP {mcp_id} probe FAILED — tools may not work at runtime. "
                                f"Real error: {real_err}"
                            )
            except Exception as e:
                logger.warning(f"Failed to connect MCP {mcp_id} ({srv.get('url')}): {_format_mcp_exception(e)}")

        if connected_mcps:
            logger.info(f"Agent {agent_def.id}: connected {len(connected_mcps)} MCP servers")

        # ── Pipeline tools (orchestration family only) ────────────────────
        # If this agent is an orchestrator with pipeline_agent_ids, pre-create
        # each pipeline agent and register one dynamic tool per agent so the
        # orchestrator LLM can call them in sequence with context propagation.
        pipeline_agent_ids = getattr(agent_def, "pipeline_agent_ids", None) or []
        if (agent_def.family_id or "").lower() == "orchestration" and pipeline_agent_ids:
            try:
                from app.services.pipeline_executor import build_pipeline_tools
                pipeline_tools, _pipeline_ctx = await build_pipeline_tools(db, pipeline_agent_ids, test_run_id=test_run_id)
                for pt in pipeline_tools:
                    toolkit.register_tool_function(pt)
                logger.info(
                    f"Orchestrator {agent_def.id}: registered {len(pipeline_tools)} pipeline tools "
                    f"for agents {pipeline_agent_ids}"
                )
            except Exception as pe:
                logger.warning(f"Failed to build pipeline tools for {agent_def.id}: {pe}")

        # Build multi-layer system prompt.
        # NOTE: do NOT manually append skill_prompt here — ReActAgent.sys_prompt
        # property calls toolkit.get_agent_skill_prompt() automatically on every
        # model call, so adding it here would double the skills content.
        sys_prompt = await build_agent_prompt(db, agent_def)

        # For orchestration agents, bump max_iters to cover the full pipeline
        effective_max_iters = max_iters
        if (agent_def.family_id or "").lower() == "orchestration" and pipeline_agent_ids:
            effective_max_iters = max(max_iters, len(pipeline_agent_ids) * 2 + 2)

        agent = ReActAgent(
            name=agent_def.id,
            sys_prompt=sys_prompt,
            model=model,
            formatter=formatter,
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=effective_max_iters,
        )

        # Attach MCP info for tracing
        agent._connected_mcps = connected_mcps

        logger.info(f"Created AgentScope agent: {agent_def.id}")
        return agent

    except Exception as e:
        logger.warning(f"Failed to create AgentScope agent {agent_def.id}: {e}")
        return None


def get_tools_for_agent(agent_def: AgentDefinition) -> list:
    """Get local Python tool functions for this agent.

    Returns an empty list if tool modules are unavailable.
    MCP remote tools are handled separately via resolve_mcp_servers().
    """
    from app.services.mcp_tool_registry import get_tools_for_mcp

    allowed = agent_def.allowed_mcps or []
    if not allowed:
        return []

    all_tools = []
    for mcp_id in allowed:
        tools = get_tools_for_mcp(mcp_id)
        if tools:
            all_tools.extend(tools)

    return all_tools
