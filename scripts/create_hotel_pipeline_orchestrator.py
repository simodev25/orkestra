"""Create the Hotel Pipeline Orchestrator in the Orkestra registry.

Usage:
  python scripts/create_hotel_pipeline_orchestrator.py
  python scripts/create_hotel_pipeline_orchestrator.py --promote   # also promote to designed

Uses ORKESTRA_API_URL env var if set, otherwise defaults to http://localhost:8200.

Pipeline agents (must exist beforehand):
  stay_discovery_agent  → Agent 1 : découverte d'hébergements via Tavily
  mobility_agent        → Agent 2 : évaluation mobilité via compute_routes (Google Maps MCP)
  weather_agent         → Agent 3 : contexte météo (minimax-m2.7)
  budget_fit_agent      → Agent 4 : scoring déterministe budget/mobilité/météo

Scores atteints sur le scénario hotel-pipeline-full-run-lisbonne : 92/100.
Optimisations clés (session 2026-04-18) :
  - TOP 3 candidats max transmis à l'agent mobilité (prévient les 500 Obot)
  - Tri par proximité centre historique + prix confirmé avant Stage 2
  - Classement final trié par overall_fit_score décroissant
"""

import os
import sys

import requests

API_URL = os.environ.get("ORKESTRA_API_URL", "http://localhost:8200")
API_KEY = os.environ.get("ORKESTRA_API_KEY", "test-orkestra-api-key")

AGENT = {
    "id": "hotel_pipeline_orchestrator",
    "name": "hotel_pipeline_orchestrator",
    "family_id": "orchestration",
    "purpose": (
        "Orchestrate a sequential hotel search pipeline that discovers accommodations, "
        "evaluates mobility, assesses weather context, and scores budget fit to produce "
        "ranked recommendations."
    ),
    "description": (
        "This orchestrator coordinates a four-stage pipeline for hotel recommendation. "
        "It routes a user request through Agent 1 (stay discovery), enriches candidates "
        "with Agent 2 (mobility evaluation), adds weather context via Agent 3, and computes "
        "final fit scores through Agent 4 (budget and fit scoring). Context is accumulated "
        "and passed sequentially between agents, with error handling at each stage to prevent "
        "pipeline blocking."
    ),
    "skill_ids": [
        "sequential_routing",
        "context_propagation",
    ],
    "selection_hints": {
        "routing_keywords": [
            "hotel", "hébergement", "lisbonne", "alfama", "pipeline", "orchestration",
            "mobilité", "météo", "budget", "séjour", "voyage", "recommandation",
        ],
        "workflow_ids": [
            "hotel_search_v1",
            "travel_planning_v1",
            "business_travel_v1",
        ],
        "use_case_hint": "hotel search pipeline orchestration with multi-agent sequential coordination",
        "requires_grounded_evidence": True,
    },
    "pipeline_agent_ids": [
        "stay_discovery_agent",
        "mobility_agent",
        "weather_agent",
        "budget_fit_agent",
    ],
    "allowed_mcps": [],
    "allow_code_execution": False,
    "forbidden_effects": [
        "publish", "approve", "external_act", "book", "purchase", "reserve", "commit",
    ],
    "criticality": "medium",
    "cost_profile": "medium",
    "llm_provider": "ollama",
    "llm_model": "minimax-m2.7",
    "limitations": [
        "Cannot directly execute agent actions; only orchestrates context passing and routing decisions",
        "Pipeline may produce incomplete results if any upstream agent fails or returns empty candidates",
        "Weather forecasts become unreliable beyond 7-10 days, affecting Agent 3 confidence",
        "Mobility scores depend on geocoding accuracy of accommodation names provided by Agent 1",
    ],
    "prompt_content": """You are the Hotel Pipeline Orchestrator, responsible for coordinating a sequential multi-agent pipeline to produce high-quality hotel recommendations tailored to user requests. Your pipeline consists of four specialized agents executed in strict order: Stay Discovery Agent, Mobility Agent, Weather Context Agent, and Budget Fit Agent.

PIPELINE EXECUTION FLOW:

STAGE 1 — STAY DISCOVERY (stay_discovery_agent): Receive the initial user request containing destination, travel dates, budget constraints, and any preference signals. Format this into a structured search request and invoke the Stay Discovery Agent via its MCP interface (Tavily Search). Collect the returned ranked list of accommodation candidates, normalizing their attributes (name, price, type, rating). If the agent returns an error or empty list, return a failure response to the user with a graceful error message.

STAGE 2 — MOBILITY EVALUATION (mobility_agent): Before passing candidates to Stage 2, select the TOP 3 candidates only (choose those with confirmed numeric prices, sorted by proximity to the historic center and within budget). Passing more than 3 candidates to the mobility agent causes compute_routes overload — strictly limit to 3. Pass only these 3 candidates. For each candidate, invoke the Mobility Agent to compute travel times from airport and city center (DRIVE mode), walking time from center (WALK mode), and derive a walkability hint with mobility score. Aggregate these into each candidate record. If mobility data is unavailable for a specific candidate, mark it as partial and continue with remaining candidates.

STAGE 3 — WEATHER CONTEXT (weather_agent): Take the destination and stay dates, and invoke the Weather Context Agent to fetch weather forecasts, compute a comfort score (0–1), and identify risk flags (rain, storms, heat waves). Attach this weather summary to the accumulated context. If weather data is unavailable or confidence is very low, note the limitation but proceed.

STAGE 4 — BUDGET FIT SCORING (budget_fit_agent): Combine all accumulated signals: price from Stage 1, mobility_score from Stage 2, weather_score from Stage 3, and the user's budget constraints. Invoke the Budget Fit Agent to compute deterministic composite fit scores with explanatory rationale. Rank candidates by fit_score descending.

CONTEXT PROPAGATION: Maintain a running context object throughout the pipeline. After each stage, merge the stage's output into the context object before passing it to the next agent. Ensure field names are consistent across stages to avoid mismatches.

ERROR HANDLING: If any stage fails or returns empty results, do not block the pipeline entirely. Instead, flag the affected candidates or the entire stage as partial, log the limitation, and continue with available data. Provide the user with transparent notes about data gaps or confidence limitations at each stage.

OUTPUT: Return a final structured response containing the ranked list of candidates with all enriched attributes, confidence indicators, and any data quality notes. Do not book, reserve, or commit to any external service. NEVER promise or mention booking links, direct reservation URLs, or external site links — you cannot access them and any such promise will not be fulfilled.

CRITICAL — FINAL RANKING: Before returning, you MUST sort the candidates list by overall_fit_score (or fit_score) DESCENDING — highest score first. The candidate with fit_rank=1 must appear first in the list, fit_rank=2 second, etc. Never present candidates in an unsorted or arbitrary order.""",
    "version": "1.0.9",
    "status": "draft",
}

SCENARIO = {
    "name": "hotel-pipeline-full-run-lisbonne",
    "description": (
        "Teste le pipeline complet : l'orchestrateur doit appeler les 4 agents dans l'ordre "
        "(stay_discovery → mobility → weather → budget_fit) et retourner un classement "
        "d'hébergements avec scores. Score cible : 92/100 (validé 2026-04-18)."
    ),
    "agent_id": "hotel_pipeline_orchestrator",
    "input_prompt": (
        "Je cherche un hébergement à Lisbonne pour 2 personnes du 10 au 15 mai 2026. "
        "Budget maximum 180€ par nuit. Je veux être proche du centre historique (Alfama) "
        "et de l'aéroport. Donne-moi les 3 meilleures options avec scores de mobilité, "
        "météo et budget."
    ),
    "timeout_seconds": 600,
    "max_iterations": 5,
    "assertions": [
        {
            "type": "output_contains",
            "expected": "mobilité",
            "critical": True,
        },
        {
            "type": "output_contains",
            "expected": "météo",
            "critical": True,
        },
        {
            "type": "output_contains",
            "expected": "budget",
            "critical": True,
        },
        {
            "type": "output_contains",
            "expected": "180",
            "critical": True,
        },
        {
            "type": "max_duration_ms",
            "expected": "600000",
            "critical": False,
        },
    ],
    "expected_tools": [
        "run_stay_discovery_agent",
        "run_mobility_agent",
        "run_weather_agent",
        "run_budget_fit_agent",
    ],
    "tags": [
        "pipeline", "hotel", "lisbonne", "alfama", "orchestration",
        "smoke_test", "full_pipeline", "92_score",
    ],
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
    print("Pipeline agents (must exist):")
    for pid in AGENT["pipeline_agent_ids"]:
        print(f"  - {pid}")
    print()
    print("Score cible : 92/100 (scénario hotel-pipeline-full-run-lisbonne)")
    print("Optimisations actives :")
    print("  · TOP 3 candidats max vers agent mobilité (prévient surcharge Obot)")
    print("  · Tri: prix confirmé + proximité centre historique")
    print("  · Classement final trié par overall_fit_score décroissant")


if __name__ == "__main__":
    main()
