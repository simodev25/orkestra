"""Document Parser MCP -- parses and extracts content from documents."""

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock


async def parse_document(document_id: str, extract_mode: str = "full") -> ToolResponse:
    """Parse a document and extract its content.

    Args:
        document_id: The ID of the document to parse.
        extract_mode: Extraction mode -- 'full', 'summary', or 'metadata'.
    """
    # In production, this would call a real document parsing service
    result = {
        "document_id": document_id,
        "extract_mode": extract_mode,
        "pages": 12,
        "content_summary": f"Document {document_id} parsed successfully in {extract_mode} mode. "
                          f"Contains 12 pages of structured content.",
        "extracted_fields": {
            "title": "Sample Document",
            "date": "2026-04-04",
            "type": "financial_report",
        },
    }
    import json
    return ToolResponse(content=[TextBlock(type="text", text=json.dumps(result, indent=2))])


async def classify_document(document_id: str) -> ToolResponse:
    """Classify a document by type and extract metadata.

    Args:
        document_id: The ID of the document to classify.
    """
    result = {
        "document_id": document_id,
        "classification": "financial_report",
        "confidence": 0.92,
        "language": "fr",
        "metadata": {
            "page_count": 12,
            "has_tables": True,
            "has_signatures": False,
        },
    }
    import json
    return ToolResponse(content=[TextBlock(type="text", text=json.dumps(result, indent=2))])
