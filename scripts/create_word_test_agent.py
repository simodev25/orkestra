"""Create a Word MCP test agent in the Orkestra registry.

Usage:
  python scripts/create_word_test_agent.py
  python scripts/create_word_test_agent.py --promote

Env vars:
  ORKESTRA_API_URL       (default: http://localhost:8200)
  ORKESTRA_API_KEY       (default: test-orkestra-api-key)
  ORKESTRA_WORD_MCP_ID   (default: ms1rbfml)
"""

from __future__ import annotations

import os
import sys

import requests

API_URL = os.environ.get("ORKESTRA_API_URL", "http://localhost:8200")
API_KEY = os.environ.get("ORKESTRA_API_KEY", "test-orkestra-api-key")
MCP_WORD = os.environ.get("ORKESTRA_WORD_MCP_ID", "ms1rbfml")

AGENT = {
    "id": "word_test_agent",
    "name": "Word MCP Test Agent",
    "family_id": "analysis",
    "purpose": (
        "Tester en lecture seule les outils Word MCP (list_docs, read_doc) et "
        "retourner un résultat JSON clair, sans appeler write_doc."
    ),
    "description": (
        "Agent de smoke test read-only pour vérifier la connectivité et l'usage des outils "
        "Microsoft Word via MCP."
    ),
    "skill_ids": [
        "requirements_extraction",
        "source_comparison",
        "context_gap_detection",
    ],
    "selection_hints": {
        "routing_keywords": [
            "word", "microsoft word", "onedrive", "docx", "document",
            "list_docs", "read_doc",
        ],
        "workflow_ids": [
            "company_intelligence_v1",
        ],
        "use_case_hint": "word mcp smoke test",
        "requires_grounded_evidence": True,
    },
    "allowed_mcps": [MCP_WORD],
    "allow_code_execution": False,
    "forbidden_effects": ["write", "publish", "approve", "external_act"],
    "criticality": "medium",
    "cost_profile": "low",
    "llm_provider": "ollama",
    "llm_model": "gpt-oss:20b",
    "limitations": [
        "Dépend d'un compte Microsoft connecté côté MCP Word",
        "Impossible de lire/écrire sans droits OneDrive valides",
        "Ne crée pas de contenu métier complexe",
    ],
    "prompt_content": """You are the Word MCP Test Agent.

Goal: use Word MCP tools correctly and return concise JSON.

Rules:
1. For listing documents, call list_docs first.
2. list_docs has no arguments: call it with an empty object {} only.
   Never send malformed input like {"": ""}.
3. If user asks to read a file, call read_doc with doc_id.
4. Do NOT call write_doc. This agent is read-only. If asked to write, respond with an error in JSON explaining you are not authorized to write.
5. If a tool fails, report the exact error in JSON.

Final output must be raw JSON only, for example:
{
  "operation": "list_docs",
  "success": true,
  "docs_count": 3,
  "docs": [
    {"id": "...", "name": "..."}
  ],
  "error": null
}
""",
    "skills_content": (
        "requirements_extraction: detect whether user wants list/read/write\n"
        "context_gap_detection: ask for missing doc_id or doc_name when needed\n"
        "source_comparison: if multiple docs match, present candidates clearly"
    ),
    "version": "1.0.0",
    "status": "draft",
}

SCENARIO = {
    "name": "Word MCP smoke test — list docs",
    "description": (
        "Vérifie qu'un agent peut appeler list_docs via le MCP Word et répondre en JSON."
    ),
    "agent_id": "word_test_agent",
    "input_prompt": (
        "Liste les documents Word disponibles dans OneDrive. "
        "Appelle list_docs puis réponds en JSON brut."
    ),
    "timeout_seconds": 120,
    "max_iterations": 6,
    "assertions": [
        {"type": "tool_called", "target": "list_docs", "critical": True},
        {"type": "final_status_is", "expected": "completed", "critical": True},
        {"type": "max_duration_ms", "expected": "90000", "critical": False},
    ],
    "expected_tools": ["list_docs"],
    "tags": ["word", "mcp", "onedrive", "smoke_test"],
}


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    return headers


def _post(path: str, payload: dict | None = None) -> requests.Response:
    return requests.post(f"{API_URL}{path}", json=payload, headers=_headers(), timeout=30)


def ensure_word_mcp_enabled() -> bool:
    print(f"Ensuring Word MCP '{MCP_WORD}' is available and enabled...")

    details = requests.get(f"{API_URL}/api/mcp-catalog/{MCP_WORD}", headers=_headers(), timeout=30)
    if details.status_code == 404:
        print("  Not in local catalog yet — syncing/importing from Obot...")
        sync_resp = _post("/api/mcp-catalog/sync")
        if not sync_resp.ok:
            print(f"  SYNC FAILED ({sync_resp.status_code}): {sync_resp.text}")
            return False

        import_resp = _post("/api/mcp-catalog/import", {"obot_server_ids": [MCP_WORD]})
        if not import_resp.ok:
            print(f"  IMPORT FAILED ({import_resp.status_code}): {import_resp.text}")
            return False

    enable_resp = _post(f"/api/mcp-catalog/{MCP_WORD}/enable")
    if not enable_resp.ok:
        print(f"  ENABLE FAILED ({enable_resp.status_code}): {enable_resp.text}")
        return False

    print("  Word MCP enabled in Orkestra.")
    return True


def create_or_update_agent() -> bool:
    print(f"Creating/updating agent '{AGENT['id']}' on {API_URL}...")
    response = _post("/api/agents", AGENT)

    if response.status_code == 201:
        body = response.json()
        print(f"  Created: {body.get('name')} (status={body.get('status')})")
        return True

    if response.status_code == 409 or "already exists" in response.text.lower():
        print("  Already exists — updating via PATCH...")
        update = requests.patch(
            f"{API_URL}/api/agents/{AGENT['id']}",
            json=AGENT,
            headers=_headers(),
            timeout=30,
        )
        if update.ok:
            body = update.json()
            print(f"  Updated: {body.get('name')} (status={body.get('status')})")
            return True

        print(f"  UPDATE FAILED ({update.status_code}): {update.text}")
        return False

    print(f"  FAILED ({response.status_code}): {response.text}")
    return False


def promote_agent(target_status: str) -> None:
    print(f"Promoting agent to '{target_status}'...")
    response = requests.patch(
        f"{API_URL}/api/agents/{AGENT['id']}/status",
        json={"status": target_status},
        headers=_headers(),
        timeout=30,
    )
    if response.ok:
        print(f"  Status: {response.json().get('status', 'unknown')}")
    else:
        print(f"  FAILED ({response.status_code}): {response.text}")


def create_scenario() -> str | None:
    print(f"Creating test scenario '{SCENARIO['name']}'...")
    response = _post("/api/test-lab/scenarios", SCENARIO)

    if response.status_code in (200, 201):
        body = response.json()
        scenario_id = body.get("id")
        print(f"  Created: {scenario_id} ({len(SCENARIO['assertions'])} assertions)")
        return scenario_id

    print(f"  FAILED ({response.status_code}): {response.text}")
    return None


def main() -> None:
    promote = "--promote" in sys.argv

    if not ensure_word_mcp_enabled():
        sys.exit(1)

    if not create_or_update_agent():
        sys.exit(1)

    if promote:
        promote_agent("designed")

    scenario_id = create_scenario()

    print("\nDone!")
    print(f"  Agent:    {API_URL}/api/agents/{AGENT['id']}")
    if scenario_id:
        print(f"  Scenario: {API_URL}/api/test-lab/scenarios/{scenario_id}")
    print(f"  UI:       http://localhost:3300/agents/{AGENT['id']}")


if __name__ == "__main__":
    main()
