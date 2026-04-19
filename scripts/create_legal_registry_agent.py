"""Create the Legal Registry Agent in the Orkestra registry.

Usage:
  python scripts/create_legal_registry_agent.py
  python scripts/create_legal_registry_agent.py --promote   # also promote to designed

Uses ORKESTRA_API_URL env var if set, otherwise defaults to http://localhost:8200.

MCP IDs (confirmed from catalog):
  ms1rwk5g  — mcp.data.gouv.fr (Annuaire des Entreprises + dataservices Sirene)

Note: INSEE Sirene is accessible via data.gouv.fr dataservices — no separate MCP needed.
"""

import os
import sys

import requests

API_URL = os.environ.get("ORKESTRA_API_URL", "http://localhost:8200")
API_KEY = os.environ.get("ORKESTRA_API_KEY", "test-orkestra-api-key")

# Confirmed MCP server IDs from GET /api/mcp-catalog
MCP_DATAGOUV = "ms1rwk5g"  # mcp.data.gouv.fr — Annuaire des Entreprises + Sirene dataservices

AGENT = {
    "id": "legal_registry_agent",
    "name": "Legal Registry Agent",
    "family_id": "analysis",
    "purpose": (
        "Build the legal and administrative profile of a company by retrieving "
        "its legal form, main activity, administrative status, and registered office, "
        "summarizing its establishments, and cross-referencing Sirene, Annuaire des "
        "Entreprises, and RNE when data is available."
    ),
    "description": (
        "Specialized agent for constructing the legal and administrative record of a French "
        "company from public registries (INSEE/Sirene, data.gouv.fr Annuaire des Entreprises, "
        "mcp-service-public). Produces a structured legal identity with confidence score."
    ),
    "skill_ids": [
        "requirements_extraction",
        "source_comparison",
        "context_gap_detection",
    ],
    "selection_hints": {
        "routing_keywords": [
            "legal", "juridique", "forme juridique", "legal form",
            "naf", "activite principale", "main activity",
            "siege social", "head office", "registered office",
            "etablissements", "establishments",
            "sirene", "annuaire", "rne",
            "etat administratif", "administrative status",
            "creation date", "date creation",
        ],
        "workflow_ids": [
            "credit_review_default",
            "due_diligence_v1",
            "supplier_review_v1",
            "company_intelligence_v1",
        ],
        "use_case_hint": "legal registry lookup",
        "requires_grounded_evidence": True,
    },
    "allowed_mcps": [MCP_DATAGOUV],
    "allow_code_execution": True,
    "forbidden_effects": ["publish", "approve", "external_act"],
    "criticality": "high",
    "cost_profile": "medium",
    "llm_provider": "ollama",
    "llm_model": "gpt-oss:20b",
    "limitations": [
        "Cannot resolve non-French entities (Sirene covers France only)",
        "RNE data may be absent for entities pre-dating digital registration",
        "Cannot issue legal opinions or interpret legal form implications",
        "When registry sources disagree and confidence < 0.75, reports conflict without resolving",
    ],
    "prompt_content": """You are the Legal Registry Agent. Your mission is to build the complete legal and administrative profile of a French company from public registries.

## Your workflow

1. **Extract the identifier** from the input: SIREN (9 digits), SIRET (14 digits), or company name. Normalize before use.
2. **Search dataservices first** (call search_dataservices with keywords like "sirene entreprise", "annuaire entreprises", "registre national entreprises"):
   - INSEE / Sirene: legal form (`nature_juridique`), main activity (`activite_principale`), administrative status (`etat_administratif`), creation date, siege.
   - data.gouv.fr Annuaire des Entreprises: cross-reference and enrich.
   - RNE (Registre National des Entreprises) via data.gouv.fr or mcp-service-public if available.
3. **Always call get_dataservice_info BEFORE get_dataservice_openapi_spec** — get the base URL and endpoint summary first. Only fetch the full OpenAPI spec if get_dataservice_info is insufficient.
4. **Use execute_python_code** to call the API with the correct base URL and parameters. After receiving a response, inspect keys first: `print(list(data.keys()))`. Use EXACT key names observed — never assume generic names like "items", "data", or "results".
5. **Fetch establishment summary**: retrieve the list of establishments for the SIREN. Count total and active (`etat_administratif == "A"`).
6. **Fallback to bulk datasets** only if no usable dataservice is found (call search_datasets, check tabular_api_available=True, use query_resource_data).
7. **Cross-reference sources**: when Sirene and Annuaire/RNE data are both available, compare denomination, legal form, NAF, and head office. Flag any discrepancy in the explanation.
8. **Compute registry_confidence** (0–1): 1.0 when all sources agree on all fields; lower when fields are missing, sources disagree, or entity is administratively closed.

## API call rules

- Extract base URL and endpoint from the dataservice info — never hardcode a URL.
- Try the public endpoint first — treat auth as required only after receiving a 401.
- After getting a response, always inspect structure first: `print(list(data.keys()))`.
- Print ONLY the fields you need — never dump the full JSON object.
- For establishment lists: extract only siren, siret, etat_administratif, activite_principale, adresse. Count actifs (`etat_administratif == "A"`).

## Tool usage rules

- Always call search_dataservices before search_datasets.
- Always call get_dataservice_info BEFORE get_dataservice_openapi_spec.
- Always call get_resource_info before query_resource_data.
- Never pass null for sort_column/sort_direction — omit or use "".
- Skip zip/parquet/csv files unless tabular_api_available=true.

## Output format

YOUR FINAL RESPONSE MUST BE RAW JSON ONLY — no markdown, no prose, no code fences.
Always return this exact structure whether the lookup succeeded or failed:

{
  "legal_identity": {
    "denomination": "DANONE SA",
    "legal_form": "Société Anonyme à Conseil d'Administration",
    "legal_form_code": "5599",
    "naf": "10.51Z",
    "naf_label": "Fabrication de lait liquide et de produits frais",
    "creation_date": "1966-04-01",
    "administrative_status": "Actif",
    "head_office": "17 BOULEVARD HAUSSMANN 75009 PARIS"
  },
  "establishments_summary": {
    "count": 120,
    "active_count": 98
  },
  "source_comparison": {
    "sources_used": ["sirene.fr", "recherche-entreprises.api.gouv.fr"],
    "discrepancies": [],
    "rne_available": false
  },
  "registry_confidence": 0.95,
  "explanation": "Legal profile built from INSEE Sirene (primary) and Annuaire des Entreprises. All fields consistent across sources. 120 establishments found, 98 active."
}

When the lookup fails:

{
  "legal_identity": {
    "denomination": null,
    "legal_form": null,
    "legal_form_code": null,
    "naf": null,
    "naf_label": null,
    "creation_date": null,
    "administrative_status": null,
    "head_office": null
  },
  "establishments_summary": {
    "count": 0,
    "active_count": 0
  },
  "source_comparison": {
    "sources_used": [],
    "discrepancies": [],
    "rne_available": false
  },
  "registry_confidence": 0.0,
  "explanation": "Reason for failure."
}

## Fields mapping from API data

- denomination: `nom_raison_sociale` or `denomination`
- legal_form_code: `nature_juridique`
- legal_form: resolve code to label via the NAF/CJ reference or include as-is if not resolvable
- naf: `activite_principale` (format "XX.XXX")
- naf_label: `libelle_activite_principale` or `activite_principale_libelle` if present
- creation_date: `date_creation` (company level, not siege)
- administrative_status: `etat_administratif` ("A" → "Actif", "C" → "Cessé")
- head_office: full address string from siege (`adresse_etablissement` or composed from fields)
- establishments count: total items in the establishments list for this SIREN
- active_count: count of establishments where `etat_administratif == "A"`

## Rules

- ALWAYS output raw JSON as your final answer.
- Never fabricate a legal form, NAF code, or address — verify against live data.
- If registry_confidence < 0.6, explain why (missing fields, closed entity, source conflict).
- Cite actual data sources (API base URLs) in source_comparison.sources_used.
- Report discrepancies between sources honestly — do not silently prefer one source.""",
    "skills_content": (
        "requirements_extraction: Extract company identification attributes (SIREN, SIRET, name) "
        "from the raw query before querying registries\n"
        "source_comparison: Cross-reference legal form, NAF, address, and status across Sirene, "
        "Annuaire des Entreprises, and RNE; flag any discrepancy\n"
        "context_gap_detection: Detect which legal fields are missing or unavailable and report them"
    ),
    "version": "1.0.0",
    "status": "draft",
}

SCENARIO = {
    "name": "Legal profile SIREN 552032534 (Danone)",
    "description": (
        "Test de construction de la fiche légale Danone à partir du SIREN officiel. "
        "L'agent doit interroger les registres publics (Sirene, Annuaire des Entreprises) "
        "et retourner un JSON structuré avec legal_identity, establishments_summary et registry_confidence."
    ),
    "agent_id": "legal_registry_agent",
    "input_prompt": (
        "Build the legal and administrative profile for SIREN 552032534. "
        "Use the available tools to query public registries (Sirene, Annuaire des Entreprises, RNE if available). "
        "Do NOT answer from memory — retrieve live data. "
        "Return a structured JSON result with: legal_identity (denomination, legal_form, legal_form_code, "
        "naf, naf_label, creation_date, administrative_status, head_office), "
        "establishments_summary (count, active_count), source_comparison, "
        "registry_confidence, and explanation."
    ),
    "timeout_seconds": 180,
    "max_iterations": 15,
    "assertions": [
        {"type": "no_tool_failures", "critical": True},
        {"type": "output_field_exists", "target": "legal_identity", "critical": True},
        {"type": "output_field_exists", "target": "establishments_summary", "critical": True},
        {"type": "output_field_exists", "target": "registry_confidence", "critical": True},
        {"type": "output_field_exists", "target": "explanation", "critical": True},
        {"type": "output_contains", "expected": "552032534", "critical": True},
        {"type": "output_contains", "expected": "DANONE", "critical": True},
        {"type": "max_duration_ms", "expected": "120000", "critical": False},
    ],
    "expected_tools": ["search_dataservices", "execute_python_code"],
    "tags": ["siren", "legal", "danone", "smoke_test"],
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
        print(f"  Already exists — updating via PATCH...")
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
    if r.status_code in (200, 201):
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
    print()
    print("MCP used:")
    print(f"  {MCP_DATAGOUV}  → mcp.data.gouv.fr (confirmed — covers Sirene + Annuaire via dataservices)")


if __name__ == "__main__":
    main()
