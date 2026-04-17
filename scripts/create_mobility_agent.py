"""Create the Mobility Agent (Agent 2) in the Orkestra registry.

Usage:
  python scripts/create_mobility_agent.py
  python scripts/create_mobility_agent.py --promote   # also promote to designed

Uses ORKESTRA_API_URL env var if set, otherwise defaults to http://localhost:8200.

MCP IDs:
  ms1dftjc  → Google Maps Grounding Lite
               Tools: compute_routes, search_places, lookup_weather
               Confirm: GET http://localhost:8200/api/mcp-catalog
"""

import os
import sys

import requests

API_URL = os.environ.get("ORKESTRA_API_URL", "http://localhost:8200")
API_KEY = os.environ.get("ORKESTRA_API_KEY", "test-orkestra-api-key")

MCP_MAPS = "ms1dftjc"  # Google Maps Grounding Lite (confirmed from catalog)

AGENT = {
    "id": "mobility_agent",
    "name": "Mobility Agent",
    "family_id": "analysis",
    "purpose": (
        "Evaluate the accessibility of accommodation options from relevant points of interest "
        "by geocoding locations via search_places, computing travel times via compute_routes, "
        "and returning comparable mobility indicators for each option."
    ),
    "description": (
        "Agent 2 of the hotel search pipeline. Takes a list of accommodation candidates "
        "(from Agent 1 — Stay Discovery Agent) and enriches each one with mobility data: "
        "travel times from airport and city center (DRIVE mode), walking time from center "
        "(WALK mode), walkability hint, and a mobility score. "
        "Uses Google Maps Grounding Lite MCP for accurate routing and place search."
    ),
    "skill_ids": [
        "source_comparison",
        "context_gap_detection",
    ],
    "selection_hints": {
        "routing_keywords": [
            "distance", "travel time", "accessibility", "airport", "station",
            "city center", "centre-ville", "aéroport", "gare", "mobilité",
            "walkability", "transport", "navette", "taxi", "metro", "bus",
            "proximité", "minutes", "km", "trajet",
        ],
        "workflow_ids": [
            "hotel_search_v1",
            "travel_planning_v1",
            "business_travel_v1",
        ],
        "use_case_hint": "accommodation mobility scoring",
        "requires_grounded_evidence": True,
    },
    "allowed_mcps": [MCP_MAPS],
    "allow_code_execution": False,
    "forbidden_effects": ["publish", "approve", "external_act", "book", "purchase"],
    "criticality": "medium",
    "cost_profile": "low",
    "llm_provider": "ollama",
    "llm_model": "gpt-oss:20b",
    "limitations": [
        "Travel modes limited to DRIVE and WALK — no public transit routing",
        "compute_routes requires a valid place name or address; may fail for unknown locations",
        "Does not book or reserve — mobility evaluation only",
        "Weather data available for next 7 days only (lookup_weather)",
        "Maximum 10 options evaluated per call",
    ],
    "prompt_content": """You are the Mobility Agent (Agent 2 of the hotel search pipeline).
Your mission: given a list of accommodation options and points of interest, evaluate the accessibility of each option using Google Maps tools and return structured mobility indicators.

⚠ MANDATORY RULES — NO EXCEPTIONS:
1. You MUST call compute_routes at least once BEFORE producing any output.
2. Do NOT invent travel times, distances, or mobility scores from memory.
3. If a tool returns an Error on the FIRST call, try it once more with simplified arguments.
   If it still fails on the SECOND call, treat ALL options as failed and output the
   "when all options fail" JSON immediately. Do NOT loop more than 2 attempts per tool.

## Available tools

- search_places(textQuery, locationBias?, languageCode?, regionCode?)
  → Find the exact address and place ID of a hotel or point of interest.
  → Use this FIRST to resolve vague location_text into a precise address.
  → Call with: search_places(textQuery="your query string")
  → Example: search_places(textQuery="city center Lisbon")

- compute_routes(origin, destination, travelMode?)
  → Compute travel time and distance between two places.
  → travelMode: "DRIVE" (default) or "WALK"
  → Use for: airport→hotel (DRIVE), city_center→hotel (DRIVE and WALK)

- lookup_weather(location, date?, hour?, unitsSystem?)
  → Optional: retrieve weather conditions for a location. Use only if weather context is relevant.

## Tool failure protocol

If search_places or compute_routes returns an Error:
- Attempt 1: retry with a simpler textQuery (e.g. just the city name)
- Attempt 2: if still failing, this means the tool is unavailable (API key issue or network)
- STOP immediately — do not make more attempts
- Output the "when all options fail" JSON with the actual error in explanation

## Input format

You receive a JSON object with:
- destination (str): city or area name
- points_of_interest (list): e.g. ["city_center", "airport", "train_station"]
- options (list): each with:
  - option_id (str): unique identifier
  - name (str): hotel or accommodation name
  - location_text (str): address or area description

## Your workflow

### Step 1 — Resolve POI locations
For each point_of_interest in the input:
- "city_center" → search_places(textQuery="city center [destination]")
- "airport"     → search_places(textQuery="main international airport [destination]")
- "train_station" → search_places(textQuery="main train station [destination]")

### Step 2 — Resolve hotel locations
For each option:
- Call search_places(textQuery="[option.name] [option.location_text]") to get the precise address.
- Store the resolved address for use in compute_routes.

### Step 3 — Compute routes
For each option × each point_of_interest:
- Call compute_routes(origin="[POI address]", destination="[hotel address]", travelMode="DRIVE")
- For city_center, also call compute_routes with travelMode="WALK" to assess walkability.
- Extract duration (minutes) and distance (km) from the response.

### Step 4 — Assess walkability
Based on WALK duration from city_center:
- "excellent": < 10 minutes
- "good":      10–20 minutes
- "moderate":  20–35 minutes
- "poor":      > 35 minutes or walk not available

### Step 5 — Compute mobility_score (0–1)
Start at 1.0, then apply deductions per point_of_interest:
- DRIVE > 30 min: −0.10
- DRIVE > 45 min: −0.20 (replaces the above)
- DRIVE > 60 min: −0.30 (replaces the above)
Apply bonus:
- walkability_hint = "excellent": +0.10
- walkability_hint = "good":      +0.05
Clamp to [0.0, 1.0].

### Step 6 — Compute mobility_confidence (0–1)
- 1.0: all routes resolved, all durations retrieved
- 0.7–0.9: most routes resolved, 1–2 options had partial data
- 0.4–0.6: several options failed geocoding or routing
- < 0.4: majority of options could not be evaluated

## Output format

YOUR FINAL RESPONSE MUST BE RAW JSON ONLY — no markdown, no prose, no code fences.

{
  "mobility_results": [
    {
      "option_id": "stay_001",
      "name": "Hotel Bairro Alto",
      "resolved_address": "Rua da Misericórdia 14, 1200-272 Lisboa",
      "airport_drive_minutes": 25,
      "airport_drive_km": 12.4,
      "city_center_drive_minutes": 5,
      "city_center_walk_minutes": 8,
      "train_station_drive_minutes": 12,
      "walkability_hint": "excellent",
      "mobility_score": 0.95
    }
  ],
  "search_queries_used": [
    "search_places: Hotel Bairro Alto Bairro Alto Lisbonne",
    "compute_routes: Humberto Delgado Airport → Rua da Misericórdia 14 Lisboa (DRIVE)",
    "compute_routes: Praça do Comércio Lisboa → Rua da Misericórdia 14 Lisboa (WALK)"
  ],
  "mobility_confidence": 0.91,
  "explanation": "All 3 options geocoded and routed via Google Maps. Option stay_003 (Cascais) flagged as far from airport (45 min DRIVE) — mobility_score reduced."
}

When a route or geocoding fails for an option:
{
  "option_id": "stay_003",
  "name": "Hotel Cascais",
  "resolved_address": null,
  "airport_drive_minutes": null,
  "airport_drive_km": null,
  "city_center_drive_minutes": null,
  "city_center_walk_minutes": null,
  "train_station_drive_minutes": null,
  "walkability_hint": null,
  "mobility_score": null
}

When all options fail (tool unavailable or all geocoding failed):
{
  "mobility_results": [],
  "search_queries_used": ["search_places: city center Lisbon — Error: <paste actual error>"],
  "mobility_confidence": 0.0,
  "explanation": "Tool unavailable: search_places returned Error on 2 consecutive calls. Likely cause: Google Maps API key not configured. No mobility data could be retrieved."
}

## Rules

- ALWAYS call search_places(textQuery="...") — the parameter name is textQuery.
- ALWAYS output raw JSON as your final answer.
- Never fabricate durations or distances — use only what compute_routes returns.
- Never evaluate more than 10 options per call.
- Include null for fields where routing failed — do not estimate or guess.
- The explanation field is always required.
- If tools fail twice consecutively → output failure JSON immediately, do not retry further.""",
    "skills_content": (
        "source_comparison: Compare routing results when multiple compute_routes calls "
        "return different values for the same pair; prefer the more precise result\n"
        "context_gap_detection: Detect missing required fields (destination, options list, "
        "location_text) and report them before attempting geocoding; flag options with "
        "insufficient location data that may cause geocoding failure"
    ),
    "version": "1.1.0",
    "status": "draft",
}

SCENARIO = {
    "name": "Mobility evaluation — Lisbonne mai 2026 (3 options)",
    "description": (
        "Test d'évaluation de mobilité pour 3 hébergements à Lisbonne. "
        "L'agent doit utiliser search_places pour géocoder les hôtels et compute_routes "
        "pour calculer les temps de trajet depuis l'aéroport et le centre-ville, "
        "puis retourner un JSON structuré avec mobility_results et mobility_confidence."
    ),
    "agent_id": "mobility_agent",
    "input_prompt": (
        'Evaluate the mobility of the following accommodation options. '
        'Use Google Maps tools to geocode locations and compute routes. '
        'Return raw JSON only.\n\n'
        'Request:\n'
        '{\n'
        '  "destination": "Lisbonne",\n'
        '  "points_of_interest": ["city_center", "airport"],\n'
        '  "options": [\n'
        '    {\n'
        '      "option_id": "stay_001",\n'
        '      "name": "Hotel Bairro Alto",\n'
        '      "location_text": "Bairro Alto, Lisbonne"\n'
        '    },\n'
        '    {\n'
        '      "option_id": "stay_002",\n'
        '      "name": "Hotel Oriente",\n'
        '      "location_text": "Parque das Nações, Lisbonne"\n'
        '    },\n'
        '    {\n'
        '      "option_id": "stay_003",\n'
        '      "name": "Hotel Cascais",\n'
        '      "location_text": "Cascais, région de Lisbonne"\n'
        '    }\n'
        '  ]\n'
        '}'
    ),
    "timeout_seconds": 180,
    "max_iterations": 15,
    "assertions": [
        {"type": "no_tool_failures", "critical": True},
        {"type": "output_field_exists", "target": "mobility_results", "critical": True},
        {"type": "output_field_exists", "target": "mobility_confidence", "critical": True},
        {"type": "output_field_exists", "target": "explanation", "critical": True},
        {"type": "output_field_exists", "target": "search_queries_used", "critical": False},
        {"type": "output_contains", "expected": "stay_001", "critical": True},
        {"type": "output_contains", "expected": "mobility_score", "critical": True},
        {"type": "output_contains", "expected": "airport", "critical": True},
        {"type": "max_duration_ms", "expected": "150000", "critical": False},
    ],
    "expected_tools": ["compute_routes", "search_places"],
    "tags": ["mobility", "hotel", "lisbonne", "google_maps", "travel_time", "smoke_test"],
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


def create_or_update_scenario():
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
    elif r.status_code == 409 or "already exists" in r.text.lower():
        # Find existing and update
        list_r = requests.get(
            f"{API_URL}/api/test-lab/scenarios?agent_id={SCENARIO['agent_id']}",
            headers=_headers(),
        )
        if list_r.ok:
            items = list_r.json().get("items", [])
            match = next((s for s in items if s.get("name") == SCENARIO["name"]), None)
            if match:
                scn_id = match["id"]
                upd = requests.patch(
                    f"{API_URL}/api/test-lab/scenarios/{scn_id}",
                    json=SCENARIO,
                    headers=_headers(),
                )
                if upd.ok:
                    print(f"  Updated existing scenario: {scn_id}")
                    return scn_id
        print(f"  FAILED ({r.status_code}): {r.text}")
        return None
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

    scenario_id = create_or_update_scenario()

    print()
    print("Done!")
    print(f"  Agent:    {API_URL}/api/agents/{AGENT['id']}")
    if scenario_id:
        print(f"  Scenario: {API_URL}/api/test-lab/scenarios/{scenario_id}")
    print(f"  UI:       http://localhost:3300/agents/{AGENT['id']}")
    print()
    print(f"MCP: Google Maps Grounding Lite ({MCP_MAPS})")
    print(f"     Tools: compute_routes, search_places, lookup_weather")


if __name__ == "__main__":
    main()
