#!/usr/bin/env bash
# scripts/seed.sh — Seed the NIA demo tenant via service APIs
#
# Usage:
#   ./scripts/seed.sh
#   TENANT_MANAGER_URL=http://localhost:8003 RAG_URL=http://localhost:8002 ./scripts/seed.sh
#
# Prerequisites:
#   - Docker Compose stack running (docker compose up -d)
#   - jq installed (brew install jq)
#   - Python venv with python-jose (.venv)

set -euo pipefail

TENANT_MANAGER_URL="${TENANT_MANAGER_URL:-http://localhost:8003}"
RAG_URL="${RAG_URL:-http://localhost:8002}"
VENV="${VENV:-$(dirname "$0")/../.venv/bin/python}"

TENANT_FILE="data/seed/tenants/demo_tenant.json"
KNOWLEDGE_FILE="data/seed/knowledge/demo_knowledge.json"

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

info()    { echo -e "${BOLD}[seed]${RESET} $*"; }
success() { echo -e "${GREEN}[checkmark]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[!]${RESET} $*"; }
fail()    { echo -e "${RED}[x]${RESET} $*"; exit 1; }

# ── Dependency check ──────────────────────────────────────────────
if ! command -v jq &>/dev/null; then
  fail "jq is required. Install with: brew install jq"
fi

# ── Generate admin JWT token ──────────────────────────────────────
info "Generating admin token..."
ADMIN_TOKEN=$("$VENV" "$(dirname "$0")/gen_admin_token.py")
if [ -z "$ADMIN_TOKEN" ]; then
  fail "Could not generate admin token. Check that .venv exists and python-jose is installed."
fi
success "Admin token generated"

# ── Wait for services ─────────────────────────────────────────────
wait_for() {
  local url="$1" name="$2" retries=30
  info "Waiting for ${name}..."
  for i in $(seq 1 "$retries"); do
    if curl -sf "${url}/health" &>/dev/null; then
      success "${name} is up"
      return 0
    fi
    sleep 2
  done
  fail "${name} did not respond after $((retries * 2))s"
}

wait_for "$TENANT_MANAGER_URL" "tenant-manager"
wait_for "$RAG_URL"             "rag-service"

# ── 1. Create / upsert demo tenant ───────────────────────────────
info "Creating demo tenant..."
TENANT_ID=$(jq -r '.id' "$TENANT_FILE")

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  "${TENANT_MANAGER_URL}/api/tenants/${TENANT_ID}")

if [ "$HTTP_STATUS" -eq 200 ]; then
  warn "Tenant '${TENANT_ID}' already exists — skipping creation"
  TENANT_RESP=$(curl -sf \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    "${TENANT_MANAGER_URL}/api/tenants/${TENANT_ID}")
  API_KEY=$(echo "$TENANT_RESP" | jq -r '.data.api_key // empty')
else
  RESPONSE=$(curl -sf -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d @"$TENANT_FILE" \
    "${TENANT_MANAGER_URL}/api/tenants")
  CREATED_ID=$(echo "$RESPONSE" | jq -r '.data.id // "?"')
  API_KEY=$(echo "$RESPONSE" | jq -r '.data.api_key // empty')
  success "Tenant created: ${CREATED_ID}"
fi

# ── 2. Get or create API key ──────────────────────────────────────
if [ -z "$API_KEY" ]; then
  info "Creating API key for tenant..."
  KEY_RESP=$(curl -sf -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d '{"name":"seed-key"}' \
    "${TENANT_MANAGER_URL}/api/tenants/${TENANT_ID}/api-keys")
  API_KEY=$(echo "$KEY_RESP" | jq -r '.data.raw_key // .data.key // "demo-key"')
fi
success "API Key: ${API_KEY}"

# ── 3. Ingest knowledge base into RAG ────────────────────────────
info "Ingesting knowledge base into RAG pipeline..."
DOC_COUNT=$(jq '.activities | length' "$KNOWLEDGE_FILE")
COLLECTION="demo_turismo_docs"

RESP=$(curl -sf -X POST \
  -H "X-Tenant-ID: ${TENANT_ID}" \
  -F "tenant_id=${TENANT_ID}" \
  -F "collection_name=${COLLECTION}" \
  -F "file=@${KNOWLEDGE_FILE}" \
  "${RAG_URL}/v1/rag/ingest-json")

CHUNKS_CREATED=$(echo "$RESP" | jq -r '.data.chunks_created // .chunks_created // 0')
success "Knowledge base ingested: ${DOC_COUNT} activities -> ${CHUNKS_CREATED} chunks"
echo "  Collection: ${COLLECTION}"

# ── Done ──────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}======================================${RESET}"
echo -e "${GREEN}${BOLD}  NIA demo seed completed successfully!${RESET}"
echo -e "${GREEN}${BOLD}======================================${RESET}"
echo ""
echo -e "  Tenant ID  : ${BOLD}${TENANT_ID}${RESET}"
echo -e "  API Key    : ${BOLD}${API_KEY}${RESET} (dev only)"
echo -e "  Collection : ${BOLD}${COLLECTION}${RESET}"
echo ""
echo -e "  Widget embed snippet:"
echo -e "  ${YELLOW}<script src=\"http://localhost:5173/nia-widget.js\"${RESET}"
echo -e "  ${YELLOW}    data-tenant=\"${TENANT_ID}\"${RESET}"
echo -e "  ${YELLOW}    data-api-url=\"http://localhost:8001\">${RESET}"
echo -e "  ${YELLOW}</script>${RESET}"
echo ""
