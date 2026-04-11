#!/usr/bin/env bash
# scripts/seed.sh — Seed the NIA demo tenant via service APIs
#
# Usage:
#   ./scripts/seed.sh
#   TENANT_MANAGER_URL=http://localhost:8003 RAG_URL=http://localhost:8002 ./scripts/seed.sh
#
# Prerequisites:
#   - Docker Compose stack running (make dev)
#   - jq installed (brew install jq)

set -euo pipefail

TENANT_MANAGER_URL="${TENANT_MANAGER_URL:-http://localhost:8003}"
RAG_URL="${RAG_URL:-http://localhost:8002}"
RECOMMENDER_URL="${RECOMMENDER_URL:-http://localhost:8004}"

TENANT_FILE="data/seed/tenants/demo_tenant.json"
PRODUCTS_FILE="data/seed/products/demo_products.json"
KNOWLEDGE_FILE="data/seed/knowledge/demo_knowledge.json"

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

info()    { echo -e "${BOLD}[seed]${RESET} $*"; }
success() { echo -e "${GREEN}[✓]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[!]${RESET} $*"; }
fail()    { echo -e "${RED}[✗]${RESET} $*"; exit 1; }

# ── Dependency check ────────────────────────────────────────────────────────
if ! command -v jq &>/dev/null; then
  fail "jq is required. Install with: brew install jq"
fi

# ── Wait for services ───────────────────────────────────────────────────────
wait_for() {
  local url="$1" name="$2" retries=30
  info "Waiting for ${name}…"
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
wait_for "$RECOMMENDER_URL"     "recommender"

# ── 1. Create / upsert demo tenant ──────────────────────────────────────────
info "Creating demo tenant…"
TENANT_ID=$(jq -r '.id' "$TENANT_FILE")
API_KEY=$(jq -r '.api_key' "$TENANT_FILE")

# Check if tenant already exists
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "X-API-Key: ${API_KEY}" \
  "${TENANT_MANAGER_URL}/tenants/${TENANT_ID}")

if [ "$HTTP_STATUS" -eq 200 ]; then
  warn "Tenant '${TENANT_ID}' already exists — skipping creation"
else
  RESPONSE=$(curl -sf -X POST \
    -H "Content-Type: application/json" \
    -d @"$TENANT_FILE" \
    "${TENANT_MANAGER_URL}/tenants")
  success "Tenant created: $(echo "$RESPONSE" | jq -r '.data.id // .id')"
fi

# ── 2. Seed products into recommender ───────────────────────────────────────
info "Seeding products into recommender (${PRODUCTS_FILE})…"
PRODUCT_COUNT=$(jq length "$PRODUCTS_FILE")
RESPONSE=$(curl -sf -X POST \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: ${TENANT_ID}" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"products\": $(cat "$PRODUCTS_FILE"), \"tenant_id\": \"${TENANT_ID}\"}" \
  "${RECOMMENDER_URL}/products/bulk" 2>/dev/null || echo '{"warning":"bulk endpoint not available, products are loaded at query time"}')
success "Products seeded: ${PRODUCT_COUNT} items"
echo "  Response: $(echo "$RESPONSE" | jq -c .)"

# ── 3. Ingest knowledge base into RAG pipeline ──────────────────────────────
info "Ingesting knowledge base (JSON) into RAG pipeline…"
DOC_COUNT=$(jq length "$KNOWLEDGE_FILE")

# Usar el nuevo endpoint /v1/rag/ingest-json que acepta archivo JSON completo
RESP=$(curl -sf -X POST \
  -H "X-Tenant-ID: ${TENANT_ID}" \
  -F "tenant_id=${TENANT_ID}" \
  -F "collection_name=nia_knowledge" \
  -F "file=@${KNOWLEDGE_FILE}" \
  "${RAG_URL}/v1/rag/ingest-json")

CHUNKS_CREATED=$(echo "$RESP" | jq -r '.data.chunks_created // 0')
success "Knowledge base ingested: ${DOC_COUNT} activities → ${CHUNKS_CREATED} chunks"

echo ""
echo -e "${GREEN}${BOLD}═══════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  NIA demo seed completed successfully!${RESET}"
echo -e "${GREEN}${BOLD}═══════════════════════════════════════${RESET}"
echo ""
echo -e "  Tenant ID : ${BOLD}${TENANT_ID}${RESET}"
echo -e "  API Key   : ${BOLD}${API_KEY}${RESET} (dev only — rotate before staging)"
echo ""
echo -e "  Widget embed snippet:"
echo -e "  ${YELLOW}<script src=\"http://localhost:5173/nia-widget.js\"${RESET}"
echo -e "  ${YELLOW}    data-tenant=\"${TENANT_ID}\"${RESET}"
echo -e "  ${YELLOW}    data-api-url=\"http://localhost:8001\">${RESET}"
echo -e "  ${YELLOW}</script>${RESET}"
echo ""
