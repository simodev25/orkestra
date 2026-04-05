#!/usr/bin/env bash
set -euo pipefail

OBOT_URL="${OBOT_URL:-http://localhost:8080}"

health_code="$(curl -sS -o /dev/null -w '%{http_code}' "${OBOT_URL}/api/healthz")"
if [[ "${health_code}" != "200" ]]; then
  echo "Obot is not reachable at ${OBOT_URL} (health=${health_code})" >&2
  exit 1
fi

existing_json="$(curl -sS "${OBOT_URL}/api/mcp-servers")"

ensure_seeded() {
  local seed_key="$1"
  local payload="$2"

  local found
  found="$(printf '%s' "${existing_json}" | jq -r --arg key "${seed_key}" '[.items[] | select(.manifest.metadata.orkestra_seed_key == $key)] | length')"

  if [[ "${found}" != "0" ]]; then
    echo "skip ${seed_key} (already exists)"
    return
  fi

  local code
  code="$(curl -sS -o /tmp/obot_seed_resp.json -w '%{http_code}' \
    -X POST "${OBOT_URL}/api/mcp-servers" \
    -H 'Content-Type: application/json' \
    --data "${payload}")"

  if [[ "${code}" != "201" ]]; then
    echo "failed ${seed_key} (http ${code})" >&2
    cat /tmp/obot_seed_resp.json >&2 || true
    exit 1
  fi

  local new_id
  new_id="$(jq -r '.id' /tmp/obot_seed_resp.json)"
  echo "created ${seed_key} -> ${new_id}"

  existing_json="$(curl -sS "${OBOT_URL}/api/mcp-servers")"
}

ensure_seeded "datagouv_search_mcp" '{
  "manifest": {
    "name": "datagouv_search_mcp",
    "shortDescription": "Search datasets and public resources on data.gouv.fr",
    "description": "Open-data search capability for French public datasets.",
    "icon": "database",
    "metadata": {
      "orkestra_seed_key": "datagouv_search_mcp",
      "effect_type": "search",
      "criticality": "low",
      "approval_required": "false",
      "business_domain": "public_data",
      "version": "1.3.0"
    },
    "runtime": "remote",
    "remoteConfig": {
      "url": "https://example.com/mcp/datagouv"
    }
  }
}'

ensure_seeded "insee_sirene_lookup_mcp" '{
  "manifest": {
    "name": "insee_sirene_lookup_mcp",
    "shortDescription": "Lookup legal and administrative company data from INSEE SIRENE",
    "description": "Company legal identity retrieval for French organizations.",
    "icon": "building-2",
    "metadata": {
      "orkestra_seed_key": "insee_sirene_lookup_mcp",
      "effect_type": "read",
      "criticality": "medium",
      "approval_required": "false",
      "business_domain": "company_registry",
      "version": "2.1.1"
    },
    "runtime": "remote",
    "remoteConfig": {
      "url": "https://example.com/mcp/insee-sirene"
    }
  }
}'

ensure_seeded "service_public_company_lookup_mcp" '{
  "manifest": {
    "name": "service_public_company_lookup_mcp",
    "shortDescription": "Fetch regulatory and administrative info from service-public APIs",
    "description": "Regulatory lookup for French legal entities.",
    "icon": "file-search",
    "metadata": {
      "orkestra_seed_key": "service_public_company_lookup_mcp",
      "effect_type": "read",
      "criticality": "medium",
      "approval_required": "false",
      "business_domain": "regulatory",
      "version": "1.0.4"
    },
    "runtime": "remote",
    "remoteConfig": {
      "url": "https://example.com/mcp/service-public"
    }
  }
}'

ensure_seeded "bodacc_events_adapter" '{
  "manifest": {
    "name": "bodacc_events_adapter",
    "shortDescription": "Retrieve legal events and publications from BODACC",
    "description": "Legal events stream for insolvency and corporate status monitoring.",
    "icon": "shield-alert",
    "metadata": {
      "orkestra_seed_key": "bodacc_events_adapter",
      "effect_type": "search",
      "criticality": "high",
      "approval_required": "true",
      "business_domain": "legal_events",
      "version": "1.2.2"
    },
    "runtime": "remote",
    "remoteConfig": {
      "url": "https://example.com/mcp/bodacc"
    }
  }
}'

ensure_seeded "boamp_search_adapter" '{
  "manifest": {
    "name": "boamp_search_adapter",
    "shortDescription": "Search French procurement opportunities and awards",
    "description": "Procurement intelligence capability.",
    "icon": "briefcase",
    "metadata": {
      "orkestra_seed_key": "boamp_search_adapter",
      "effect_type": "search",
      "criticality": "medium",
      "approval_required": "false",
      "business_domain": "procurement",
      "version": "1.1.0"
    },
    "runtime": "remote",
    "remoteConfig": {
      "url": "https://example.com/mcp/boamp"
    }
  }
}'

ensure_seeded "web_search_mcp" '{
  "manifest": {
    "name": "web_search_mcp",
    "shortDescription": "General purpose web search for broad evidence collection",
    "description": "Fallback web search capability for low-trust open web data.",
    "icon": "globe",
    "metadata": {
      "orkestra_seed_key": "web_search_mcp",
      "effect_type": "search",
      "criticality": "low",
      "approval_required": "false",
      "business_domain": "open_web",
      "version": "2.0.0"
    },
    "runtime": "remote",
    "remoteConfig": {
      "url": "https://example.com/mcp/web-search"
    }
  }
}'

final_count="$(curl -sS "${OBOT_URL}/api/mcp-servers" | jq -r '.items | length')"
echo "done: ${final_count} MCP server(s) in Obot"
