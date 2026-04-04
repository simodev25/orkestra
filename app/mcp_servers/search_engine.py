"""Search Engine MCP -- semantic search across knowledge base."""

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock


async def search_knowledge(query: str, max_results: int = 5) -> ToolResponse:
    """Search the knowledge base for relevant information.

    Args:
        query: The search query.
        max_results: Maximum number of results to return.
    """
    result = {
        "query": query,
        "results": [
            {
                "id": f"doc_{i}",
                "title": f"Result {i} for '{query}'",
                "relevance": round(0.95 - i * 0.1, 2),
                "snippet": f"This document contains information relevant to {query}...",
            }
            for i in range(min(max_results, 3))
        ],
        "total_found": 3,
    }
    import json
    return ToolResponse(content=[TextBlock(type="text", text=json.dumps(result, indent=2))])
