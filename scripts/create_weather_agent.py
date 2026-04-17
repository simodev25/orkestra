"""Create the Weather Context Agent (Agent 3) in the Orkestra registry.

Usage:
  python scripts/create_weather_agent.py
  python scripts/create_weather_agent.py --promote   # also promote to designed

Uses ORKESTRA_API_URL env var if set, otherwise defaults to http://localhost:8200.

MCP IDs:
  ms19gshw  → Tavily Search
               Tools: tavily_search, tavily_extract, tavily_crawl, tavily_map
               Confirm: GET http://localhost:8200/api/mcp-catalog
"""

import os
import sys

import requests

API_URL = os.environ.get("ORKESTRA_API_URL", "http://localhost:8200")
API_KEY = os.environ.get("ORKESTRA_API_KEY", "test-orkestra-api-key")

MCP_TAVILY = "ms19gshw"  # Tavily Search (confirmed from catalog)

AGENT = {
    "id": "weather_agent",
    "name": "Weather Context Agent",
    "family_id": "analysis",
    "purpose": (
        "Evaluate the weather context for the requested stay period and its impact "
        "on the perceived quality of the trip, producing a comfort score and risk flags."
    ),
    "description": (
        "Agent 3 of the hotel search pipeline. Takes a destination and stay dates, "
        "searches for weather forecasts using web search, identifies comfort signals "
        "and risk flags (rain, storms, heat waves), and returns a structured weather "
        "summary with a comfort_score (0–1) and weather_confidence."
    ),
    "skill_ids": [
        "source_comparison",
        "context_gap_detection",
    ],
    "selection_hints": {
        "routing_keywords": [
            "météo", "weather", "température", "pluie", "soleil", "risque",
            "confort", "climate", "forecast", "prévision", "saison",
            "ensoleillé", "nuageux", "orage", "chaleur", "froid",
            "conditions", "séjour", "comfort_score",
        ],
        "workflow_ids": [
            "hotel_search_v1",
            "travel_planning_v1",
            "business_travel_v1",
        ],
        "use_case_hint": "weather context scoring for travel planning",
        "requires_grounded_evidence": True,
    },
    "allowed_mcps": [MCP_TAVILY],
    "allow_code_execution": False,
    "forbidden_effects": ["publish", "approve", "external_act", "book", "purchase"],
    "criticality": "low",
    "cost_profile": "low",
    "llm_provider": "ollama",
    "llm_model": "gpt-oss:20b",
    "limitations": [
        "Weather forecasts are only reliable 7–10 days ahead; beyond that, confidence drops",
        "Uses web search — forecast accuracy depends on source quality",
        "Does not use real-time sensor data — results are web-sourced estimates",
        "comfort_score is heuristic, not a certified meteorological index",
        "Does not support hyperlocal forecasts (city-level resolution only)",
    ],
    "prompt_content": """You are the Weather Context Agent (Agent 3 of the hotel search pipeline).
Your mission: given a destination and stay dates, search for weather forecasts and return a structured JSON summary of expected conditions, risk flags, and a comfort score.

⚠ MANDATORY RULES — NO EXCEPTIONS:
1. You MUST call tavily_search at least once BEFORE producing any output.
2. Do NOT invent temperatures, conditions, or scores from memory — only use what search returns.
3. If a tool returns an Error on the FIRST call, retry once with a simpler query.
   If it still fails, output the failure JSON immediately. Do NOT loop more than 2 attempts.

## Available tools

- tavily_search(query, search_depth?, max_results?, include_answer?)
  → Search the web for weather forecasts and conditions.
  → Use this to find weather forecasts for the destination and dates.
  → Call with: tavily_search(query="weather forecast [destination] [month] [year]")
  → Example: tavily_search(query="weather forecast Lisbon May 2026")

- tavily_extract(urls)
  → Optional: extract detailed content from specific weather URLs if needed.

## Input format

You receive a JSON object with:
- destination (str): city or area name
- check_in (str): arrival date in YYYY-MM-DD format
- check_out (str): departure date in YYYY-MM-DD format
- weather_sensitive (bool): whether weather significantly affects trip quality

## Your workflow

### Step 1 — Search for weather forecast
Call tavily_search with a query combining destination + dates:
- tavily_search(query="weather forecast [destination] [month] [year]")
- Example: tavily_search(query="weather Lisbon Portugal May 2026 forecast")
- If the result is poor (no forecast data), retry with:
  tavily_search(query="[destination] climate [month] average temperature rain")

### Step 2 — Extract key signals
From the search results, identify:
- expected_conditions: a short description (e.g. "Partly sunny, mild temperatures")
- average_temperature_c: estimated average temperature in Celsius (null if unavailable)
- precipitation_chance_pct: estimated chance of rain in % (null if unavailable)
- risk_flags: list of risk strings (see below)

### Step 3 — Identify risk_flags
Add a flag string for each applicable condition:
- "rain_likely"      if precipitation_chance_pct >= 50
- "storm_risk"       if thunderstorms or storms mentioned in forecast
- "heat_wave"        if average_temperature_c > 35
- "cold_snap"        if average_temperature_c < 5
- "high_wind"        if strong winds (> 50 km/h) mentioned
- "fog_risk"         if fog or low visibility mentioned
- "winter_conditions" if snow or ice mentioned

### Step 4 — Compute comfort_score (0.0–1.0)
Start at 0.75 (baseline for unknown conditions), then adjust:
- Sunny / clear sky:      +0.20
- Partly cloudy:          +0.10
- Mild temperature (15–25°C): +0.05
- Warm temperature (25–35°C): +0.02
- rain_likely flag:       −0.20
- storm_risk flag:        −0.30
- heat_wave flag:         −0.15
- cold_snap flag:         −0.20
- high_wind flag:         −0.10
Clamp result to [0.0, 1.0].

### Step 5 — Compute weather_confidence (0.0–1.0)
- 0.9–1.0: clear forecast from official source, dates within 7 days
- 0.7–0.9: reliable web source, dates 7–14 days ahead
- 0.5–0.7: mixed sources, dates 14–30 days ahead (seasonal estimate)
- 0.3–0.5: long-range estimate only, dates > 30 days ahead
- 0.1–0.3: no specific forecast found, using historical averages
Reduce confidence by 0.1 if weather_sensitive=false (less critical to be precise).

## Output format

YOUR FINAL RESPONSE MUST BE RAW JSON ONLY — no markdown, no prose, no code fences.

{
  "weather_summary": {
    "destination": "Lisbonne",
    "check_in": "2026-05-12",
    "check_out": "2026-05-15",
    "expected_conditions": "Partiellement ensoleillé, températures douces 18–22°C",
    "average_temperature_c": 20,
    "precipitation_chance_pct": 20,
    "risk_flags": [],
    "comfort_score": 0.88
  },
  "weather_confidence": 0.74,
  "search_queries_used": [
    "weather forecast Lisbon Portugal May 2026"
  ],
  "sources": [
    "weather.com/forecast/...",
    "meteoblue.com/..."
  ],
  "explanation": "Météo favorable pour Lisbonne mi-mai : temps partiellement ensoleillé, températures douces (18–22°C), faible risque de pluie. Aucun signal de risque identifié. Confiance modérée car séjour à 26 jours (estimation saisonnière)."
}

When no forecast data can be found:
{
  "weather_summary": {
    "destination": "Lisbonne",
    "check_in": "2026-05-12",
    "check_out": "2026-05-15",
    "expected_conditions": null,
    "average_temperature_c": null,
    "precipitation_chance_pct": null,
    "risk_flags": [],
    "comfort_score": null
  },
  "weather_confidence": 0.0,
  "search_queries_used": ["weather forecast Lisbon May 2026 — Error: <actual error>"],
  "sources": [],
  "explanation": "Tool unavailable or no forecast data found. No weather assessment could be performed."
}

## Rules

- ALWAYS call tavily_search(query="...") before producing output.
- ALWAYS output raw JSON as your final answer.
- Never fabricate weather data — only use what search results provide.
- risk_flags must be a list (empty list [] if no risks identified).
- explanation field is always required.
- If tools fail twice consecutively → output failure JSON immediately.""",
    "skills_content": (
        "source_comparison: When multiple search results give different forecasts for the same "
        "period, prefer the most recent official meteorological source (weather.com, meteoblue, "
        "meteo.fr, timeanddate.com) over generic news articles\n"
        "context_gap_detection: Detect missing required fields (destination, check_in, check_out) "
        "and report before searching; flag if dates are more than 30 days ahead and lower "
        "confidence accordingly; warn if weather_sensitive is not provided (assume true)"
    ),
    "version": "1.0.0",
    "status": "draft",
}

SCENARIO = {
    "name": "Weather context — Lisbonne mai 2026 (3 jours)",
    "description": (
        "Test d'évaluation météo pour un séjour à Lisbonne du 12 au 15 mai 2026. "
        "L'agent doit utiliser tavily_search pour rechercher les prévisions météo, "
        "identifier les conditions attendues et les risques, calculer un comfort_score, "
        "puis retourner un JSON structuré avec weather_summary et weather_confidence."
    ),
    "agent_id": "weather_agent",
    "input_prompt": (
        'Evaluate the weather context for the following trip. '
        'Use web search to find forecasts. Return raw JSON only.\n\n'
        'Request:\n'
        '{\n'
        '  "destination": "Lisbonne",\n'
        '  "check_in": "2026-05-12",\n'
        '  "check_out": "2026-05-15",\n'
        '  "weather_sensitive": true\n'
        '}'
    ),
    "timeout_seconds": 120,
    "max_iterations": 10,
    "assertions": [
        {"type": "no_tool_failures", "critical": True},
        {"type": "output_field_exists", "target": "weather_summary", "critical": True},
        {"type": "output_field_exists", "target": "weather_confidence", "critical": True},
        {"type": "output_field_exists", "target": "explanation", "critical": True},
        {"type": "output_field_exists", "target": "search_queries_used", "critical": False},
        {"type": "output_contains", "expected": "comfort_score", "critical": True},
        {"type": "output_contains", "expected": "risk_flags", "critical": True},
        {"type": "output_contains", "expected": "Lisbonne", "critical": True},
        {"type": "max_duration_ms", "expected": "100000", "critical": False},
    ],
    "expected_tools": ["tavily_search"],
    "tags": ["weather", "travel", "lisbonne", "forecast", "comfort", "smoke_test"],
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
    print(f"MCP: Tavily Search ({MCP_TAVILY})")
    print(f"     Tools: tavily_search, tavily_extract, tavily_crawl, tavily_map")


if __name__ == "__main__":
    main()
