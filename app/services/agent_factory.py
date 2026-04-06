"""Agent factory -- creates AgentScope ReActAgent from Orkestra agent definitions."""

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import AgentDefinition
from app.llm.provider import get_chat_model, get_formatter, is_agentscope_available

logger = logging.getLogger(__name__)


def _docker_safe_host(host: str) -> str:
    """Replace localhost/127.0.0.1 with host.docker.internal for Docker compat."""
    if os.path.exists("/.dockerenv") or os.environ.get("ORKESTRA_DATABASE_URL", "").startswith("postgresql"):
        return host.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
    return host


def _get_agent_specific_model(provider: str, model_name: str):
    """Create a model instance for a specific provider/model combination."""
    if not is_agentscope_available():
        return None
    try:
        if provider == "ollama":
            from agentscope.model import OllamaChatModel
            from app.core.config import get_settings
            settings = get_settings()
            host = _docker_safe_host(settings.OLLAMA_HOST)
            effective_name = model_name if "-cloud" in model_name else f"{model_name}-cloud"
            return OllamaChatModel(
                model_name=effective_name,
                host=host,
                stream=False,
            )
        elif provider == "openai":
            from agentscope.model import OpenAIChatModel
            from app.core.config import get_settings
            settings = get_settings()
            return OpenAIChatModel(
                model_name=model_name,
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
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
    """Resolve MCP server URLs from the agent's allowed_mcps IDs.

    Returns list of dicts: [{"id": "ms19ww6r", "name": "...", "url": "https://..."}]
    """
    allowed = agent_def.allowed_mcps or []
    if not allowed:
        return []

    from app.services import agent_registry_service
    try:
        catalog = await agent_registry_service.available_mcp_summaries(db)
        catalog_map = {m["id"]: m for m in catalog}
    except Exception:
        catalog_map = {}

    servers = []
    for mcp_id in allowed:
        cat = catalog_map.get(mcp_id)
        if cat:
            name = cat.get("name", mcp_id)
            # The name field contains the MCP server URL
            url = name if name.startswith("http") else None
            servers.append({"id": mcp_id, "name": name, "url": url})
        else:
            servers.append({"id": mcp_id, "name": mcp_id, "url": None})

    return servers


async def create_agentscope_agent(
    agent_def: AgentDefinition,
    db: AsyncSession,
    tools_to_register: list | None = None,
    max_iters: int = 5,
):
    """Create an AgentScope ReActAgent from an Orkestra AgentDefinition.

    Connects to MCP servers declared in allowed_mcps and registers their tools.
    Returns None if AgentScope or LLM is not available.
    """
    if not is_agentscope_available():
        logger.info(f"AgentScope not available, cannot create agent {agent_def.id}")
        return None

    if agent_def.llm_provider and agent_def.llm_model:
        model = _get_agent_specific_model(agent_def.llm_provider, agent_def.llm_model)
    else:
        model = get_chat_model()
    if model is None:
        logger.info(f"LLM not available, cannot create agent {agent_def.id}")
        return None

    formatter = get_formatter()
    if formatter is None:
        return None

    try:
        from agentscope.agent import ReActAgent
        from agentscope.tool import Toolkit
        from agentscope.memory import InMemoryMemory
        from app.services.prompt_builder import build_agent_prompt

        toolkit = Toolkit()

        # Register local tool functions
        if tools_to_register:
            for tool_func in tools_to_register:
                toolkit.register_tool_function(tool_func)

        # Register Orkestra skills via AgentScope register_agent_skill
        await _register_orkestra_skills(db, agent_def, toolkit)

        # Connect to remote MCP servers and register their tools
        mcp_servers = await resolve_mcp_servers(db, agent_def)
        connected_mcps = []
        for srv in mcp_servers:
            if not srv.get("url"):
                logger.warning(f"MCP {srv['id']} has no URL, skipping")
                continue
            try:
                from agentscope.mcp import HttpStatelessClient
                mcp_client = HttpStatelessClient(
                    name=srv["id"],
                    transport="streamable_http",
                    url=srv["url"],
                    timeout=30,
                )
                # List available tools and register them
                mcp_tools = await mcp_client.list_tools()
                logger.info(f"MCP {srv['id']} ({srv['url']}): {len(mcp_tools)} tools found")
                if mcp_tools:
                    await toolkit.register_mcp_client(
                        mcp_client=mcp_client,
                        group_name="basic",
                        namesake_strategy="rename",
                    )
                    connected_mcps.append({
                        "id": srv["id"],
                        "url": srv["url"],
                        "tools": [t.name for t in mcp_tools],
                    })
            except Exception as e:
                logger.warning(f"Failed to connect MCP {srv['id']} ({srv.get('url')}): {e}")

        if connected_mcps:
            logger.info(f"Agent {agent_def.id}: connected {len(connected_mcps)} MCP servers")

        # Build multi-layer system prompt + AgentScope skill prompt
        sys_prompt = await build_agent_prompt(db, agent_def)
        skill_prompt = toolkit.get_agent_skill_prompt()
        if skill_prompt:
            sys_prompt = f"{sys_prompt}\n\n{skill_prompt}"

        agent = ReActAgent(
            name=agent_def.id,
            sys_prompt=sys_prompt,
            model=model,
            formatter=formatter,
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=max_iters,
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
    allowed = agent_def.allowed_mcps or []
    if not allowed:
        return []

    MCP_TOOL_MAP: dict[str, list] = {}

    try:
        from app.mcp_servers.document_parser import parse_document, classify_document
        MCP_TOOL_MAP["document_parser"] = [parse_document, classify_document]
    except ImportError:
        pass

    try:
        from app.mcp_servers.consistency_checker import check_consistency, validate_fields
        MCP_TOOL_MAP["consistency_checker"] = [check_consistency, validate_fields]
    except ImportError:
        pass

    try:
        from app.mcp_servers.search_engine import search_knowledge
        MCP_TOOL_MAP["search_engine"] = [search_knowledge]
    except ImportError:
        pass

    try:
        from app.mcp_servers.weather import get_weather
        MCP_TOOL_MAP["weather"] = [get_weather]
    except ImportError:
        pass

    tools = []
    for mcp_id in allowed:
        if mcp_id in MCP_TOOL_MAP:
            tools.extend(MCP_TOOL_MAP[mcp_id])

    return tools
