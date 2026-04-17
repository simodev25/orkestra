"""Create the Budget & Fit Agent (Agent 4) in the Orkestra registry.

Usage:
  python scripts/create_budget_fit_agent.py
  python scripts/create_budget_fit_agent.py --promote   # also promote to designed

Uses ORKESTRA_API_URL env var if set, otherwise defaults to http://localhost:8200.

No MCP — pure deterministic internal logic.
All scoring rules are explicit, reproducible, and LLM-independent.
"""

import os
import sys

import requests

API_URL = os.environ.get("ORKESTRA_API_URL", "http://localhost:8200")
API_KEY = os.environ.get("ORKESTRA_API_KEY", "test-orkestra-api-key")

AGENT = {
    "id": "budget_fit_agent",
    "name": "Budget & Fit Agent",
    "family_id": "analysis",
    "purpose": (
        "Compute a deterministic composite fit score for each accommodation option "
        "by integrating budget constraints, mobility scores, and weather scores using "
        "explicit, testable rules — no tool calls required."
    ),
    "description": (
        "Agent 4 of the hotel search pipeline. Pure deterministic scoring layer. "
        "Takes budget constraints and per-option signals (price, mobility_score, weather_score) "
        "from Agents 1–3, applies explicit weighted rules, and returns a fit_score and "
        "fit_explanation for each option. No MCP, no external calls — governance layer."
    ),
    "skill_ids": [],
    "selection_hints": {
        "routing_keywords": [
            "budget", "score", "fit", "prix", "plafond", "composite",
            "recommandation", "classement", "ranking", "pondération",
            "gouvernance", "déterministe", "éligibilité", "seuil",
        ],
        "workflow_ids": [
            "hotel_search_v1",
            "travel_planning_v1",
            "business_travel_v1",
        ],
        "use_case_hint": "deterministic budget and fit scoring for accommodation options",
        "requires_grounded_evidence": False,
    },
    "allowed_mcps": [],
    "allow_code_execution": False,
    "forbidden_effects": ["publish", "approve", "external_act", "book", "purchase"],
    "criticality": "high",
    "cost_profile": "low",
    "llm_provider": "ollama",
    "llm_model": "gpt-oss:20b",
    "limitations": [
        "Scores are only as good as the input signals — garbage in, garbage out",
        "mobility_score and weather_score are optional; missing values reduce weight redistribution",
        "Does not fetch prices, routing, or weather itself — relies on upstream agents",
        "comfort_score and mobility_score must be in [0.0, 1.0] range",
        "Maximum 20 options per call",
    ],
    "prompt_content": """You are the Budget & Fit Agent (Agent 4 of the hotel search pipeline).
Your mission: given budget constraints and per-option signals, apply deterministic scoring rules to compute a budget_score, overall_fit_score, and fit_explanation for each option.

⚠ MANDATORY RULES:
1. You MUST NOT call any external tool. This agent has no MCP access.
2. You MUST follow the scoring algorithm EXACTLY as defined below — no approximations.
3. All arithmetic must be computed step by step and shown in your reasoning.
4. YOUR FINAL RESPONSE MUST BE RAW JSON ONLY — no markdown, no prose, no code fences.

## Input format

You receive a JSON object with:
- budget_per_night (float): maximum acceptable price per night in the same currency as options
- options (list): each with:
  - option_id (str): unique identifier
  - name (str, optional): hotel name for display
  - price_per_night (float): actual price per night
  - mobility_score (float | null): 0.0–1.0 from Agent 2, or null if unavailable
  - weather_score (float | null): 0.0–1.0 from Agent 3 (comfort_score), or null if unavailable

## Scoring algorithm — follow EXACTLY

### Step 1 — Compute budget_score for each option

Let ratio = price_per_night / budget_per_night

IF ratio <= 1.0 (price at or under budget):
    budget_score = 1.0 - (0.25 * ratio)
    Examples: ratio=0.0 → 1.00, ratio=0.5 → 0.875, ratio=0.8 → 0.80, ratio=1.0 → 0.75

IF ratio > 1.0 (price over budget):
    overrun = ratio - 1.0
    budget_score = max(0.0, 0.75 - (1.5 * overrun))
    Examples: ratio=1.10 → 0.60, ratio=1.25 → 0.375, ratio=1.50 → 0.0

Round budget_score to 3 decimal places. Clamp to [0.0, 1.0].

### Step 2 — Determine weights for overall_fit_score

Weights depend on which optional scores are available:

CASE A — mobility_score AND weather_score both available:
    w_budget   = 0.50
    w_mobility = 0.30
    w_weather  = 0.20

CASE B — only mobility_score available (weather_score is null):
    w_budget   = 0.60
    w_mobility = 0.40
    w_weather  = 0.00

CASE C — only weather_score available (mobility_score is null):
    w_budget   = 0.60
    w_mobility = 0.00
    w_weather  = 0.40

CASE D — neither mobility_score nor weather_score available:
    w_budget   = 1.00
    w_mobility = 0.00
    w_weather  = 0.00

### Step 3 — Compute overall_fit_score

overall_fit_score = (
    budget_score * w_budget
    + (mobility_score or 0.0) * w_mobility
    + (weather_score or 0.0) * w_weather
)

Then apply bonuses (additive, applied after weighted sum):
- IF price_per_night < budget_per_night * 0.80: bonus +0.03  (great deal)
- IF mobility_score is not null AND mobility_score >= 0.90:  bonus +0.02
- IF weather_score  is not null AND weather_score  >= 0.85:  bonus +0.02

Clamp final overall_fit_score to [0.0, 1.0].
Round to 3 decimal places.

### Step 4 — Build fit_explanation (list of strings)

Always include exactly one string per dimension evaluated:

Budget string (always present):
- price < budget * 0.80:  "prix bien sous plafond ({savings}% d'économie)"
  where savings = round((1 - ratio) * 100)
- budget * 0.80 <= price < budget: "prix sous plafond ({savings}% sous plafond)"
- price == budget:          "prix exactement au plafond"
- budget < price <= budget * 1.10: "prix légèrement au-dessus du plafond (+{overrun}%)"
  where overrun = round((ratio - 1) * 100)
- price > budget * 1.10:   "prix hors plafond (+{overrun}%)"

Mobility string (only if mobility_score is not null):
- >= 0.85: "excellente accessibilité (score {mobility_score})"
- >= 0.70: "bonne accessibilité (score {mobility_score})"
- >= 0.50: "accessibilité correcte (score {mobility_score})"
-  < 0.50: "accessibilité limitée (score {mobility_score})"

Weather string (only if weather_score is not null):
- >= 0.85: "contexte météo très favorable (confort {weather_score})"
- >= 0.70: "contexte météo favorable (confort {weather_score})"
- >= 0.50: "météo acceptable (confort {weather_score})"
-  < 0.50: "conditions météo défavorables (confort {weather_score})"

Overall recommendation string (always present, based on overall_fit_score):
- >= 0.85: "option fortement recommandée"
- >= 0.70: "option recommandée"
- >= 0.55: "option acceptable"
- >= 0.40: "option à considérer avec réserves"
-  < 0.40: "option déconseillée"

### Step 5 — Determine fit_rank

Sort all options by overall_fit_score descending.
Assign fit_rank = 1 to the highest scoring option, 2 to the second, etc.
In case of tie: lower price_per_night gets the better rank.

## Output format

YOUR FINAL RESPONSE MUST BE RAW JSON ONLY — no markdown, no prose, no code fences.

{
  "fit_results": [
    {
      "option_id": "stay_001",
      "name": "Hotel Bairro Alto",
      "price_per_night": 165,
      "budget_per_night": 180,
      "budget_score": 0.771,
      "mobility_score": 0.84,
      "weather_score": 0.88,
      "overall_fit_score": 0.817,
      "fit_rank": 1,
      "fit_explanation": [
        "prix sous plafond (8% sous plafond)",
        "bonne accessibilité (score 0.84)",
        "contexte météo très favorable (confort 0.88)",
        "option recommandée"
      ]
    }
  ],
  "scoring_weights": {
    "budget": 0.50,
    "mobility": 0.30,
    "weather": 0.20
  },
  "options_evaluated": 1,
  "top_pick": "stay_001",
  "explanation": "1 option évaluée. Poids: budget 50%, mobilité 30%, météo 20%. Option stay_001 recommandée: prix sous plafond avec bonne mobilité et météo favorable."
}

## Rules

- NEVER call external tools or APIs.
- NEVER skip the step-by-step arithmetic — show each calculation in your reasoning.
- ALWAYS output valid JSON as your final answer.
- ALWAYS include fit_rank for every option.
- ALWAYS include top_pick (option_id with fit_rank=1).
- If all options have overall_fit_score < 0.40, add "warning": "aucune option ne satisfait les critères budgétaires" to the output.
- Maximum 20 options per call.""",
    "skills_content": None,
    "version": "1.0.0",
    "status": "draft",
}

SCENARIO = {
    "name": "Budget & Fit — Lisbonne mai 2026 (3 options, budget 180€)",
    "description": (
        "Test de scoring déterministe pour 3 hébergements à Lisbonne avec un budget de 180€/nuit. "
        "L'agent doit calculer budget_score, overall_fit_score et fit_explanation pour chaque option "
        "en appliquant les règles explicites du prompt, sans outil externe."
    ),
    "agent_id": "budget_fit_agent",
    "input_prompt": (
        'Compute the budget and fit scores for the following accommodation options. '
        'Apply the deterministic scoring rules. Return raw JSON only.\n\n'
        'Request:\n'
        '{\n'
        '  "budget_per_night": 180,\n'
        '  "options": [\n'
        '    {\n'
        '      "option_id": "stay_001",\n'
        '      "name": "Hotel Bairro Alto",\n'
        '      "price_per_night": 165,\n'
        '      "mobility_score": 0.84,\n'
        '      "weather_score": 0.88\n'
        '    },\n'
        '    {\n'
        '      "option_id": "stay_002",\n'
        '      "name": "Hotel Oriente",\n'
        '      "price_per_night": 210,\n'
        '      "mobility_score": 0.71,\n'
        '      "weather_score": 0.88\n'
        '    },\n'
        '    {\n'
        '      "option_id": "stay_003",\n'
        '      "name": "Hotel Cascais",\n'
        '      "price_per_night": 140,\n'
        '      "mobility_score": 0.42,\n'
        '      "weather_score": 0.88\n'
        '    }\n'
        '  ]\n'
        '}'
    ),
    "timeout_seconds": 90,
    "max_iterations": 8,
    "assertions": [
        {"type": "output_field_exists", "target": "fit_results", "critical": True},
        {"type": "output_field_exists", "target": "top_pick", "critical": True},
        {"type": "output_field_exists", "target": "scoring_weights", "critical": True},
        {"type": "output_field_exists", "target": "explanation", "critical": True},
        {"type": "output_contains", "expected": "stay_001", "critical": True},
        {"type": "output_contains", "expected": "budget_score", "critical": True},
        {"type": "output_contains", "expected": "overall_fit_score", "critical": True},
        {"type": "output_contains", "expected": "fit_rank", "critical": True},
        {"type": "output_contains", "expected": "fit_explanation", "critical": True},
        {"type": "max_duration_ms", "expected": "80000", "critical": False},
    ],
    "expected_tools": [],
    "tags": ["budget", "fit", "scoring", "deterministic", "lisbonne", "governance", "smoke_test"],
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


def _verify_scores():
    """Print expected scores for the test scenario to verify agent output."""
    budget = 180
    options = [
        {"id": "stay_001", "price": 165, "mob": 0.84, "wth": 0.88},
        {"id": "stay_002", "price": 210, "mob": 0.71, "wth": 0.88},
        {"id": "stay_003", "price": 140, "mob": 0.42, "wth": 0.88},
    ]
    print()
    print("Expected scores (for verification):")
    results = []
    for o in options:
        ratio = o["price"] / budget
        if ratio <= 1.0:
            bs = 1.0 - 0.25 * ratio
        else:
            bs = max(0.0, 0.75 - 1.5 * (ratio - 1.0))
        bs = round(bs, 3)

        # Case A: both available
        w_b, w_m, w_w = 0.50, 0.30, 0.20
        ofs = bs * w_b + o["mob"] * w_m + o["wth"] * w_w

        # Bonuses
        if o["price"] < budget * 0.80:
            ofs += 0.03
        if o["mob"] >= 0.90:
            ofs += 0.02
        if o["wth"] >= 0.85:
            ofs += 0.02

        ofs = round(min(1.0, max(0.0, ofs)), 3)
        results.append((o["id"], bs, ofs, o["price"]))
        print(f"  {o['id']}: ratio={ratio:.2f} → budget_score={bs:.3f}, overall_fit_score={ofs:.3f}")

    results.sort(key=lambda x: (-x[2], x[3]))
    print(f"  top_pick: {results[0][0]} (fit={results[0][2]:.3f})")


def main():
    promote = "--promote" in sys.argv

    ok = create_or_update_agent()
    if not ok:
        sys.exit(1)

    if promote:
        promote_agent("designed")

    scenario_id = create_or_update_scenario()

    _verify_scores()

    print()
    print("Done!")
    print(f"  Agent:    {API_URL}/api/agents/{AGENT['id']}")
    if scenario_id:
        print(f"  Scenario: {API_URL}/api/test-lab/scenarios/{scenario_id}")
    print(f"  UI:       http://localhost:3300/agents/{AGENT['id']}")
    print()
    print("No MCP — pure deterministic logic (governance layer)")
    print("Weights: budget 50% · mobility 30% · weather 20%")


if __name__ == "__main__":
    main()
