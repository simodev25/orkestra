"""Agent factory -- creates AgentScope ReActAgent from Orkestra agent definitions."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import AgentDefinition
from app.llm.provider import get_chat_model, get_formatter, is_agentscope_available

logger = logging.getLogger(__name__)


def _get_agent_specific_model(provider: str, model_name: str):
    """Create a model instance for a specific provider/model combination."""
    if not is_agentscope_available():
        return None
    try:
        if provider == "ollama":
            from agentscope.model import OllamaChatModel
            from app.core.config import get_settings
            settings = get_settings()
            return OllamaChatModel(
                model_name=model_name,
                host=settings.OLLAMA_HOST,
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


async def create_agentscope_agent(
    agent_def: AgentDefinition,
    db: AsyncSession,
    tools_to_register: list | None = None,
):
    """Create an AgentScope ReActAgent from an Orkestra AgentDefinition.

    Returns None if AgentScope or LLM is not available (caller should use fallback).
    """
    if not is_agentscope_available():
        logger.info(f"AgentScope not available, cannot create agent {agent_def.id}")
        return None

    if agent_def.llm_provider and agent_def.llm_model:
        model = _get_agent_specific_model(agent_def.llm_provider, agent_def.llm_model)
    else:
        model = get_chat_model()  # platform default
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

        # Build toolkit with registered tools
        toolkit = Toolkit()
        if tools_to_register:
            for tool_func in tools_to_register:
                toolkit.register_tool_function(tool_func)

        # Build multi-layer system prompt from agent definition
        sys_prompt = await build_agent_prompt(db, agent_def)

        agent = ReActAgent(
            name=agent_def.id,
            sys_prompt=sys_prompt,
            model=model,
            formatter=formatter,
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=5,
        )

        logger.info(f"Created AgentScope agent: {agent_def.id}")
        return agent

    except Exception as e:
        logger.warning(f"Failed to create AgentScope agent {agent_def.id}: {e}")
        return None


def get_tools_for_agent(agent_def: AgentDefinition) -> list:
    """Get the MCP tool functions that this agent is allowed to use.

    Returns an empty list if tool modules are unavailable (resilient by design).
    """
    allowed = agent_def.allowed_mcps or []
    if not allowed:
        return []

    # Attempt to import each tool module individually so missing modules don't
    # prevent other tools from being loaded.
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
