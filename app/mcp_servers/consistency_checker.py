"""Consistency Checker MCP -- detects contradictions across data sources."""

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock


async def check_consistency(data_sources: str, check_type: str = "cross_document") -> ToolResponse:
    """Check consistency across multiple data sources.

    Args:
        data_sources: Comma-separated list of data source IDs to compare.
        check_type: Type of consistency check -- 'cross_document', 'field_validation', or 'temporal'.
    """
    sources = [s.strip() for s in data_sources.split(",")]
    result = {
        "check_type": check_type,
        "sources_checked": sources,
        "inconsistencies_found": 2,
        "findings": [
            {
                "severity": "high",
                "field": "revenue_2025",
                "description": (
                    f"Revenue figure differs between {sources[0]} and "
                    f"{sources[1] if len(sources) > 1 else 'N/A'}"
                ),
                "values": {"source_a": "12.5M", "source_b": "13.1M"},
            },
            {
                "severity": "low",
                "field": "company_name",
                "description": "Minor spelling variation in company name",
                "values": {"source_a": "Acme Corp", "source_b": "ACME Corporation"},
            },
        ],
    }
    import json
    return ToolResponse(content=[TextBlock(type="text", text=json.dumps(result, indent=2))])


async def validate_fields(entity_id: str, fields: str) -> ToolResponse:
    """Validate specific fields of an entity against known rules.

    Args:
        entity_id: The entity ID to validate.
        fields: Comma-separated list of field names to validate.
    """
    field_list = [f.strip() for f in fields.split(",")]
    result = {
        "entity_id": entity_id,
        "fields_checked": field_list,
        "all_valid": True,
        "validations": [
            {"field": f, "valid": True, "rule": "format_check"} for f in field_list
        ],
    }
    import json
    return ToolResponse(content=[TextBlock(type="text", text=json.dumps(result, indent=2))])
