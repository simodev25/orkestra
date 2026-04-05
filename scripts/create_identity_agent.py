import requests, json

agent = {
    "id": "identity_resolution_agent",
    "name": "Identity Resolution Agent",
    "family_id": "analysis",
    "purpose": "Resolve the target company with certainty by normalizing queries, searching by name/SIREN/SIRET, managing homonyms, selecting the correct legal unit, and returning an identity confidence score.",
    "description": "Specialized agent for resolving company identity with high confidence using French public data sources (INSEE/Sirene, data.gouv.fr, service-public.fr).",
    "skill_ids": ["requirements_extraction", "source_comparison", "context_gap_detection"],
    "selection_hints": {
        "routing_keywords": ["identity", "entity", "alias", "match", "matching", "deduplication", "duplicate", "ambiguity", "ambiguous", "normalize", "normalization", "resolve", "resolution", "company name", "legal entity", "registry match"],
        "workflow_ids": ["credit_review_default", "due_diligence_v1", "supplier_review_v1", "company_intelligence_v1"],
        "use_case_hint": "identity resolution",
        "requires_grounded_evidence": True
    },
    "allowed_mcps": [],
    "forbidden_effects": ["act", "generate"],
    "criticality": "high",
    "cost_profile": "medium",
    "limitations": [
        "Cannot resolve non-French entities",
        "Cannot issue legal judgments",
        "Cannot disambiguate without human review when confidence < 0.7"
    ],
    "prompt_content": (
        "You are the Identity Resolution Agent. Your mission is to resolve a company target "
        "with maximum certainty.\n\n"
        "## Your workflow\n"
        "1. Normalize the input query (clean names, remove stopwords, standardize acronyms)\n"
        "2. Search by SIREN/SIRET if provided, otherwise search by name using INSEE Sirene API\n"
        "3. If multiple results (homonyms), evaluate each candidate and rank by relevance\n"
        "4. Select the main legal unit (siege social) as the reference unit\n"
        "5. Compute an identity_confidence score between 0 and 1\n"
        "6. Return a structured result with the resolved company data or explain why resolution failed\n\n"
        "## Output format\n"
        "{\n"
        "  \"resolved\": true|false,\n"
        "  \"company_name\": \"...\",\n"
        "  \"siren\": \"...\",\n"
        "  \"main_siret\": \"...\",\n"
        "  \"identity_confidence\": 0.93,\n"
        "  \"alternatives_rejected\": []\n"
        "}\n\n"
        "## Data sources\n"
        "- INSEE Sirene API (official French company register)\n"
        "- data.gouv.fr (public datasets)\n"
        "- service-public.fr (administrative information)\n\n"
        "## Rules\n"
        "- Always prefer authoritative sources (INSEE) over secondary ones\n"
        "- Never guess a SIREN; always verify against official data\n"
        "- If confidence < 0.7, return resolved: false and explain why\n"
        "- Handle homonyms by cross-referencing additional attributes\n"
        "- Cite your data sources in the reasoning trace"
    ),
    "skills_content": (
        "requirements_extraction: Extract company identification attributes from the raw query\n"
        "source_comparison: Evaluate multiple candidates when homonyms exist, comparing attributes to select the best match\n"
        "context_gap_detection: Detect missing information needed for unambiguous resolution\n"
        "quality_review: Verify resolved data is consistent and confidence score is justified"
    ),
    "version": "1.0.0",
    "status": "designed",
    "owner": None,
    "last_test_status": "not_tested"
}

r = requests.post("http://localhost:8200/api/agents", json=agent)
print(r.status_code)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
