"""Agent factory -- creates AgentScope ReActAgent from Orkestra agent definitions."""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import AgentDefinition
from app.llm.provider import get_chat_model, get_formatter, is_agentscope_available

logger = logging.getLogger(__name__)


async def create_agentscope_agent(
    agent_def: AgentDefinition,
    tools_to_register: list | None = None,
):
    """Create an AgentScope ReActAgent from an Orkestra AgentDefinition.

    Returns None if AgentScope or LLM is not available (caller should use fallback).
    """
    if not is_agentscope_available():
        logger.info(f"AgentScope not available, cannot create agent {agent_def.id}")
        return None

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

        # Build toolkit with registered tools
        toolkit = Toolkit()
        if tools_to_register:
            for tool_func in tools_to_register:
                toolkit.register_tool_function(tool_func)

        # Build system prompt from agent definition
        sys_prompt = _build_system_prompt(agent_def)

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


def _build_system_prompt(agent_def: AgentDefinition) -> str:
    """Build a system prompt from agent definition metadata."""
    parts = [
        f"You are {agent_def.name}.",
        f"\nYour mission: {agent_def.purpose}",
    ]

    if agent_def.description:
        parts.append(f"\n{agent_def.description}")

    if agent_def.skills:
        parts.append(f"\nYour skills: {', '.join(agent_def.skills)}")

    if agent_def.limitations:
        parts.append(f"\nLimitations: {', '.join(agent_def.limitations)}")

    parts.append(
        "\n\nYou must produce structured, factual output. "
        "Always include confidence levels and cite sources when possible. "
        "If you are uncertain, say so explicitly."
    )

    return "\n".join(parts)


def get_tools_for_agent(agent_def: AgentDefinition) -> list:
    """Get the MCP tool functions that this agent is allowed to use."""
    from app.mcp_servers.document_parser import parse_document, classify_document
    from app.mcp_servers.consistency_checker import check_consistency, validate_fields
    from app.mcp_servers.search_engine import search_knowledge

    # Map MCP IDs to tool functions
    MCP_TOOL_MAP = {
        "document_parser": [parse_document, classify_document],
        "consistency_checker": [check_consistency, validate_fields],
        "search_engine": [search_knowledge],
    }

    tools = []
    allowed = agent_def.allowed_mcps or []
    for mcp_id in allowed:
        if mcp_id in MCP_TOOL_MAP:
            tools.extend(MCP_TOOL_MAP[mcp_id])

    return tools
