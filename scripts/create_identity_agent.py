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
    "allowed_mcps": ["ms1rwk5g"],
    "allow_code_execution": True,
    "forbidden_effects": ["publish", "approve", "external_act"],
    "criticality": "high",
    "cost_profile": "medium",
    "llm_provider": "ollama",
    "llm_model": "gpt-oss:20b",
    "limitations": [
        "Cannot resolve non-French entities",
        "Cannot issue legal judgments",
        "Cannot disambiguate without human review when confidence < 0.7",
    ],
    "prompt_content": """You are the Identity Resolution Agent. Your mission is to resolve a company target with maximum certainty.

## Your workflow
1. Normalize the input query (clean names, remove stopwords, standardize acronyms).
2. If a SIREN/SIRET is provided, go directly to step 3. Otherwise search by name.
3. **PRIORITY — search for a live API first**: call search_dataservices with keywords matching
   the entity type (e.g. "entreprise siren", "societe siret", "company registry").
   A dataservice exposes a queryable REST API; prefer it over bulk files.
4. **When you have a dataservice**: ALWAYS call get_dataservice_info FIRST to get the base URL and
   endpoint summary. NEVER call get_dataservice_openapi_spec without having called get_dataservice_info
   first — the full OpenAPI spec is large and should only be fetched if get_dataservice_info does not
   provide enough information to build the HTTP request.
   Then use execute_python_code to call the API with the base URL and your query parameters.
5. **Fallback — bulk datasets**: if no usable dataservice is found, call search_datasets.
   For each candidate resource: call get_resource_info first, verify tabular_api_available=true,
   then call query_resource_data. Never pass sort_column=null or sort_direction=null — omit them.
   Skip zip/parquet files immediately (not queryable via Tabular API).
6. Evaluate all results, rank candidates, handle homonyms by cross-referencing attributes.
7. Select the main legal unit (siege social) as the reference unit.
8. Compute identity_confidence (0–1) and return the mandatory JSON result.

## API call rules (when using execute_python_code for dataservices)
- Extract the base URL and endpoint from the OpenAPI spec — never hardcode a URL.
- Map your query input (name, identifier, SIREN, SIRET…) to the parameter names in the spec.
- Try the public endpoint first — only treat auth as required if you receive a 401.
- If an endpoint returns no results, try an alternative endpoint from the same spec.
- After getting the API response, always inspect the structure first: `print(list(data.keys()))`.
  Use the EXACT key names you observed in the output — NEVER assume names like "items", "companies",
  "data", or "results". For example, if the print shows `dict_keys(['results', 'total_results'])`,
  then access `data["results"]`, not `data.get("companies", [])` or `data.get("items", [])`.
  Then print ONLY the fields you need (siren, name, siret, address, status) — do NOT dump the
  entire JSON object. Large responses will overflow context.
  Example: print only result["siren"], result["nom_raison_sociale"], result["siege"]["siret"].

## Tool usage rules
- Always call search_dataservices before search_datasets.
- Always call get_dataservice_info BEFORE get_dataservice_openapi_spec — never skip this step.
- Only call get_dataservice_openapi_spec if get_dataservice_info is insufficient to build the request.
- Always call get_resource_info before query_resource_data.
- Never pass null for sort_column/sort_direction — omit or use "".
- Bulk zip/parquet/csv files: skip unless tabular_api_available=true.

## Output format
YOUR FINAL RESPONSE MUST BE RAW JSON ONLY — no markdown, no prose, no code fences.
Always return this exact structure whether resolution succeeded or failed:

{
  "resolved": true,
  "company_name": "ACME SAS",
  "siren": "123456789",
  "main_siret": "12345678900019",
  "identity_confidence": 0.95,
  "alternatives_rejected": [],
  "sources": ["recherche-entreprises.api.gouv.fr"],
  "explanation": "Resolved via SIREN lookup on recherche-entreprises.api.gouv.fr. Single match found, siege confirmed."
}

When resolution fails:

{
  "resolved": false,
  "company_name": null,
  "siren": "<input_value_or_null>",
  "main_siret": null,
  "identity_confidence": 0.0,
  "alternatives_rejected": [],
  "sources": [],
  "explanation": "Reason for failure."
}

The explanation field is ALWAYS required — never null. For successful resolutions, describe the source used and why the match is confident.

## Rules
- ALWAYS output raw JSON as your final answer.
- Never guess a SIREN/SIRET — verify against live data.
- If confidence < 0.7, set resolved=false and explain why.
- Handle homonyms: cross-reference name, location, NAF code, legal form.
- Cite actual data sources (API base URLs) in the sources array.""",
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
        "L'agent doit utiliser les outils MCP + execute_python_code pour interroger "
        "les sources publiques et retourner un JSON structure."
    ),
    "agent_id": "identity_resolution_agent",
    "input_prompt": (
        "Resolve the company identity for SIREN 552032534. "
        "Use the available tools to query public data sources. "
        "Do NOT answer from memory — retrieve live data. "
        "Return a structured JSON result with resolved, company_name, siren, "
        "main_siret, identity_confidence, sources, and explanation."
    ),
    "timeout_seconds": 180,
    "max_iterations": 15,
    "assertions": [
        {"type": "no_tool_failures", "critical": True},
        {"type": "output_field_exists", "target": "resolved", "critical": True},
        {"type": "output_field_exists", "target": "identity_confidence", "critical": True},
        {"type": "output_contains", "expected": "552032534", "critical": True},
        {"type": "max_duration_ms", "expected": "120000", "critical": False},
    ],
    "expected_tools": ["search_dataservices", "execute_python_code"],
    "tags": ["siren", "identity", "danone", "smoke_test"],
}


def _headers():
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


def create_or_update_agent():
    print(f"Creating/updating agent '{AGENT['id']}' on {API_URL}...")
    r = requests.post(f"{API_URL}/api/agents", json=AGENT, headers=_headers())
    if r.status_code == 201:
        print(f"  Created: {r.json()['name']} (status={r.json()['status']})")
        return True
    elif r.status_code == 409 or "already exists" in r.text.lower():
        print(f"  Already exists — updating prompt via PATCH...")
        r2 = requests.patch(
            f"{API_URL}/api/agents/{AGENT['id']}",
            json=AGENT,
            headers=_headers(),
        )
        if r2.ok:
            print(f"  Updated: {r2.json().get('name')} (status={r2.json().get('status')})")
            return True
        else:
            print(f"  UPDATE FAILED ({r2.status_code}): {r2.text}")
            return False
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

    ok = create_or_update_agent()
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
