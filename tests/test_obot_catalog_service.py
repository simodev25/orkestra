from app.services.obot_catalog_service import _extract_servers_payload, _normalize_obot_payload


def test_extract_servers_payload_items_shape():
    payload = {
        "items": [
            {"id": "mcp_a", "name": "A"},
            {"id": "mcp_b", "name": "B"},
        ]
    }

    items = _extract_servers_payload(payload)
    assert len(items) == 2
    assert items[0]["id"] == "mcp_a"
    assert items[1]["id"] == "mcp_b"


def test_normalize_obot_payload_from_obot_apiclient_shape():
    raw = {
        "id": "srv_search",
        "alias": "Search Server",
        "manifest": {
            "shortDescription": "Search public sources",
            "description": "Indexed public-data search.",
            "metadata": {
                "effect_type": "search",
                "criticality": "high",
                "approval_required": "true",
                "version": "2026.04.01",
            },
        },
        "deploymentStatus": "Ready",
        "links": {"self": "http://obot:8080/api/all-mcps/servers/srv_search"},
    }

    normalized = _normalize_obot_payload(raw)
    assert normalized.id == "srv_search"
    assert normalized.name == "Search Server"
    assert normalized.purpose == "Search public sources"
    assert normalized.description == "Indexed public-data search."
    assert normalized.effect_type == "search"
    assert normalized.criticality == "high"
    assert normalized.approval_required is True
    assert normalized.state == "active"
    assert normalized.health_status == "healthy"
    assert normalized.version == "2026.04.01"
    assert normalized.obot_url == "http://obot:8080/api/all-mcps/servers/srv_search"
