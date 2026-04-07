"""Create the Identity Resolution Agent in the Orkestra registry.

Usage:
  python scripts/create_identity_agent.py
  python scripts/create_identity_agent.py --promote   # also promote to designed

Uses ORKESTRA_API_URL env var if set, otherwise defaults to http://localhost:8200.
"""

import json
import os
import sys

import requests

API_URL = os.environ.get("ORKESTRA_API_URL", "http://localhost:8200")
API_KEY = os.environ.get("ORKESTRA_API_KEY", "test-orkestra-api-key")

AGENT = {
    "id": "identity_resolution_agent",
    "name": "Identity Resolution Agent",
    "family_id": "analysis",
    "purpose": (
        "Resolve the target company with certainty by normalizing queries, "
        "searching by name/SIREN/SIRET, managing homonyms, selecting the "
        "correct legal unit, and returning an identity confidence score."
    ),
    "description": (
        "Specialized agent for resolving company identity with high confidence "
        "using French public data sources (INSEE/Sirene, data.gouv.fr, service-public.fr)."
    ),
    "skill_ids": [
        "requirements_extraction",
        "source_comparison",
        "context_gap_detection",
    ],
    "selection_hints": {
        "routing_keywords": [
            "identity", "entity", "alias", "match", "matching",
            "deduplication", "duplicate", "ambiguity", "ambiguous",
            "normalize", "normalization", "resolve", "resolution",
            "company name", "legal entity", "registry match",
        ],
        "workflow_ids": [
            "credit_review_default",
            "due_diligence_v1",
            "supplier_review_v1",
            "company_intelligence_v1",
        ],
        "use_case_hint": "identity resolution",
        "requires_grounded_evidence": True,
    },
    "allowed_mcps": ["search_engine", "document_parser"],
    "forbidden_effects": ["publish", "approve", "external_act"],
    "criticality": "high",
    "cost_profile": "medium",
    "limitations": [
        "Cannot resolve non-French entities",
        "Cannot issue legal judgments",
        "Cannot disambiguate without human review when confidence < 0.7",
    ],
    "prompt_content": """You are the Identity Resolution Agent. Your mission is to resolve a company target with maximum certainty.

## Your workflow
1. Normalize the input query (clean names, remove stopwords, standardize acronyms)
2. Search by SIREN/SIRET if provided, otherwise search by name using available tools
3. If multiple results (homonyms), evaluate each candidate and rank by relevance
4. Select the main legal unit (siege social) as the reference unit
5. Compute an identity_confidence score between 0 and 1
6. Return a structured result with the resolved company data or explain why resolution failed

## Output format
{
  "resolved": true|false,
  "company_name": "...",
  "siren": "...",
  "main_siret": "...",
  "identity_confidence": 0.93,
  "alternatives_rejected": []
}

## Rules
- Always prefer authoritative sources (INSEE) over secondary ones
- Never guess a SIREN; always verify against official data
- If confidence < 0.7, return resolved: false and explain why
- Handle homonyms by cross-referencing additional attributes
- Cite your data sources in the reasoning trace""",
    "skills_content": (
        "requirements_extraction: Extract company identification attributes from the raw query\n"
        "source_comparison: Evaluate multiple candidates when homonyms exist, "
        "comparing attributes to select the best match\n"
        "context_gap_detection: Detect missing information needed for unambiguous resolution"
    ),
    "version": "1.0.0",
    "status": "draft",
}

SCENARIO = {
    "name": "Resolve SIREN 552032534 (Danone)",
    "description": (
        "Test de resolution identite entreprise a partir du SIREN officiel Danone. "
        "L'agent doit utiliser les outils MCP pour interroger les sources publiques."
    ),
    "agent_id": "identity_resolution_agent",
    "input_prompt": (
        "Resolve the company with SIREN 552032534. Use the available tools to query "
        "public data sources. Do NOT answer from memory. Return a structured identity "
        "resolution result with confidence score."
    ),
    "timeout_seconds": 120,
    "max_iterations": 5,
    "assertions": [
        {"type": "no_tool_failures", "critical": True},
        {"type": "output_field_exists", "target": "resolved", "critical": True},
        {"type": "max_duration_ms", "expected": "60000", "critical": False},
    ],
    "expected_tools": ["search_knowledge"],
    "tags": ["siren", "identity", "danone", "smoke_test"],
}


def _headers():
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


def create_agent():
    print(f"Creating agent '{AGENT['id']}' on {API_URL}...")
    r = requests.post(f"{API_URL}/api/agents", json=AGENT, headers=_headers())
    if r.status_code == 201:
        print(f"  Created: {r.json()['name']} (status={r.json()['status']})")
        return True
    elif r.status_code == 409 or "already exists" in r.text.lower():
        print(f"  Already exists, skipping creation.")
        return True
    else:
        print(f"  FAILED ({r.status_code}): {r.text}")
        return False


def promote_agent(target_status: str):
    print(f"Promoting agent to '{target_status}'...")
    r = requests.patch(
        f"{API_URL}/api/agents/{AGENT['id']}/status",
        json={"status": target_status},
        headers=_headers(),
    )
    if r.ok:
        print(f"  Status: {r.json().get('status', 'unknown')}")
    else:
        print(f"  FAILED ({r.status_code}): {r.text}")


def create_scenario():
    print(f"Creating test scenario '{SCENARIO['name']}'...")
    r = requests.post(
        f"{API_URL}/api/test-lab/scenarios",
        json=SCENARIO,
        headers=_headers(),
    )
    if r.status_code == 201 or r.status_code == 200:
        data = r.json()
        print(f"  Created: {data.get('id')} ({len(SCENARIO['assertions'])} assertions)")
        return data.get("id")
    else:
        print(f"  FAILED ({r.status_code}): {r.text}")
        return None


def main():
    promote = "--promote" in sys.argv

    ok = create_agent()
    if not ok:
        sys.exit(1)

    if promote:
        promote_agent("designed")

    scenario_id = create_scenario()

    print()
    print("Done!")
    print(f"  Agent:    {API_URL}/api/agents/{AGENT['id']}")
    if scenario_id:
        print(f"  Scenario: {API_URL}/api/test-lab/scenarios/{scenario_id}")
    print(f"  UI:       http://localhost:3300/agents/{AGENT['id']}")


if __name__ == "__main__":
    main()
