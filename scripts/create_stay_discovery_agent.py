"""Create the Stay Discovery Agent in the Orkestra registry.

Usage:
  python scripts/create_stay_discovery_agent.py
  python scripts/create_stay_discovery_agent.py --promote   # also promote to designed

Uses ORKESTRA_API_URL env var if set, otherwise defaults to http://localhost:8200.

MCP IDs:
  Look up the Tavily Search MCP server ID from GET /api/mcp-catalog or the Obot UI,
  then update MCP_TAVILY below before running.
"""

import os
import sys

import requests

API_URL = os.environ.get("ORKESTRA_API_URL", "http://localhost:8200")
API_KEY = os.environ.get("ORKESTRA_API_KEY", "test-orkestra-api-key")

# MCP server ID — verify against your Obot catalog before running.
# GET http://localhost:8200/api/mcp-catalog  to list available server IDs.
MCP_TAVILY = "ms_tavily_search"  # Tavily Search MCP — replace with real ID from catalog

AGENT = {
    "id": "stay_discovery_agent",
    "name": "Stay Discovery Agent",
    "family_id": "analysis",
    "purpose": (
        "Identify relevant accommodation options for a given destination and dates "
        "by querying web search, extracting multiple candidates, normalising their "
        "main attributes, and discarding results clearly outside the requested scope."
    ),
    "description": (
        "Agent 1 of the hotel search pipeline. Takes a structured search request "
        "(destination, dates, budget, preferences) and returns a ranked list of "
        "accommodation candidates ready for downstream evaluation. "
        "Uses Tavily Search MCP to query live web sources."
    ),
    "skill_ids": [
        "requirements_extraction",
        "source_comparison",
        "context_gap_detection",
    ],
    "selection_hints": {
        "routing_keywords": [
            "hotel", "hébergement", "accommodation", "stay", "séjour",
            "destination", "check-in", "check-out", "nuit", "night",
            "budget", "hôtel", "hostel", "airbnb", "logement",
            "chambre", "room", "booking", "réservation",
        ],
        "workflow_ids": [
            "hotel_search_v1",
            "travel_planning_v1",
            "business_travel_v1",
        ],
        "use_case_hint": "accommodation discovery",
        "requires_grounded_evidence": True,
    },
    "allowed_mcps": [MCP_TAVILY],
    "allow_code_execution": False,
    "forbidden_effects": ["publish", "approve", "external_act", "book", "purchase"],
    "criticality": "medium",
    "cost_profile": "low",
    "llm_provider": "ollama",
    "llm_model": "gpt-oss:20b",
    "limitations": [
        "Does not book or reserve — discovery only",
        "Price accuracy depends on Tavily search results; always verify on booking site",
        "Cannot access gated booking platforms that block web crawlers",
        "Does not handle real-time availability — treat prices as indicative",
        "Maximum 10 candidates per search",
    ],
    "prompt_content": """You are the Stay Discovery Agent (Agent 1 of the hotel search pipeline).
Your sole mission: given a structured accommodation request, find and return a ranked list of concrete hotel candidates from live web sources.

## Input format

You receive a JSON object with these fields:
- destination (str): city or area name
- check_in (str): YYYY-MM-DD
- check_out (str): YYYY-MM-DD
- budget_per_night (number): maximum price per night in EUR (or currency specified)
- preferences (object): optional hints — near_city_center, stars, amenities, etc.

## Your workflow

1. **Reformulate the search query** in natural language from the input fields.
   Combine destination + dates + budget + key preferences into 2–3 distinct search queries.
   Example: "hotel Lisbonne centre-ville 12-15 mai 2026 moins de 180 euros par nuit"

2. **Search with Tavily** — call the Tavily search tool with each query.
   Use queries in both the destination's language and French/English for broader coverage.
   Target sites: booking.com, hotels.com, expedia.com, trip.com, accorhotels.com, and local sources.

3. **Extract candidates** from the search results.
   For each result that looks like an actual hotel listing, extract:
   - name (exact hotel name)
   - address (as complete as available)
   - stars (integer 1–5, null if unknown)
   - price_per_night (number, null if not found)
   - currency (default EUR)
   - distance_center_km (float, null if unknown)
   - amenities (list of strings — wifi, breakfast, parking, pool, spa, etc.)
   - booking_url (direct link to the listing)
   - source (domain of the source page)

4. **Eliminate out-of-scope results**:
   - Price clearly above budget_per_night (> 20% over)
   - Not in the requested destination city
   - Not a real accommodation (skip listicles, blog posts without booking links)
   - Duplicate entries for the same hotel (keep the one with more data)

5. **Normalise**:
   - Standardise hotel names (remove "hotel" prefix duplicates)
   - Convert prices to EUR if in another currency (use approximate rate, flag with currency field)
   - Sort by: within budget first, then by proximity to centre if near_city_center=true, then by stars descending

6. **Compute discovery_confidence** (0–1):
   - 1.0: multiple sources, prices confirmed, addresses complete
   - 0.7–0.9: good coverage but some fields missing
   - 0.4–0.6: few results or prices unconfirmed
   - < 0.4: very limited results, treat as partial

## Output format

YOUR FINAL RESPONSE MUST BE RAW JSON ONLY — no markdown, no prose, no code fences.

{
  "candidates": [
    {
      "name": "Hotel Lisboa Plaza",
      "address": "Travessa do Salitre 7, 1269-066 Lisboa",
      "stars": 4,
      "price_per_night": 145,
      "currency": "EUR",
      "distance_center_km": 0.3,
      "amenities": ["wifi", "breakfast", "air_conditioning"],
      "booking_url": "https://www.booking.com/hotel/pt/lisboa-plaza.html",
      "source": "booking.com"
    }
  ],
  "search_queries_used": [
    "hotel Lisbonne centre 12-15 mai 2026 moins de 180 euros",
    "hotel Lisbon city center May 2026 budget 180 EUR"
  ],
  "total_found": 8,
  "within_budget": 5,
  "discovery_confidence": 0.82,
  "explanation": "Found 8 candidates via Tavily search across booking.com and expedia.com. 5 are within the 180 EUR/night budget. Sorted by proximity to city centre as requested."
}

When no results are found:

{
  "candidates": [],
  "search_queries_used": ["..."],
  "total_found": 0,
  "within_budget": 0,
  "discovery_confidence": 0.0,
  "explanation": "Reason: no results found or all results out of scope."
}

## Rules

- ALWAYS output raw JSON as your final answer.
- Never fabricate hotel names, addresses, or prices — only include data found in search results.
- Never include more than 10 candidates.
- Never output booking credentials, payment info, or personal data.
- If budget_per_night is null or missing, include all found results without price filtering.
- The explanation field is always required and must cite which sources were used.""",
    "skills_content": (
        "requirements_extraction: Extract destination, dates, budget, and preference attributes "
        "from the raw input before building search queries\n"
        "source_comparison: Deduplicate and compare hotel entries across multiple search result "
        "sources; prefer entries with more complete data\n"
        "context_gap_detection: Detect missing required fields (destination, dates) and report "
        "them before attempting search"
    ),
    "version": "1.0.0",
    "status": "draft",
}

SCENARIO = {
    "name": "Stay discovery — Lisbonne mai 2026 (budget 180€)",
    "description": (
        "Test de découverte d'hébergements pour Lisbonne, 3 nuits en mai 2026, "
        "budget 180€/nuit, préférence centre-ville. "
        "L'agent doit interroger Tavily, extraire des candidats réels et retourner "
        "un JSON structuré avec candidates, within_budget et discovery_confidence."
    ),
    "agent_id": "stay_discovery_agent",
    "input_prompt": (
        'Find accommodation options for the following request. '
        'Do NOT answer from memory — use the search tools to retrieve live results. '
        'Return raw JSON only.\n\n'
        'Request:\n'
        '{\n'
        '  "destination": "Lisbonne",\n'
        '  "check_in": "2026-05-12",\n'
        '  "check_out": "2026-05-15",\n'
        '  "budget_per_night": 180,\n'
        '  "preferences": {\n'
        '    "near_city_center": true\n'
        '  }\n'
        '}'
    ),
    "timeout_seconds": 120,
    "max_iterations": 10,
    "assertions": [
        {"type": "no_tool_failures", "critical": True},
        {"type": "output_field_exists", "target": "candidates", "critical": True},
        {"type": "output_field_exists", "target": "within_budget", "critical": True},
        {"type": "output_field_exists", "target": "discovery_confidence", "critical": True},
        {"type": "output_field_exists", "target": "explanation", "critical": True},
        {"type": "output_field_exists", "target": "search_queries_used", "critical": False},
        {"type": "output_contains", "expected": "Lisbo", "critical": True},
        {"type": "max_duration_ms", "expected": "90000", "critical": False},
    ],
    "expected_tools": ["tavily_search"],
    "tags": ["hotel", "discovery", "lisbonne", "smoke_test"],
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
    print("NOTE: Verify MCP ID before running the agent:")
    print(f"  {MCP_TAVILY}  → Tavily Search (check: GET {API_URL}/api/mcp-catalog)")


if __name__ == "__main__":
    main()
