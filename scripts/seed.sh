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
PRODUCTS_FILE="data/seed/products/demo_products.json"

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

# ── 4. Seed products into PostgreSQL ─────────────────────────────
info "Seeding products into PostgreSQL..."
PRODUCT_COUNT=$(jq 'length' "$PRODUCTS_FILE")
TENANT_SCHEMA="tenant_${TENANT_ID}"

python3 - << PYEOF
import json, subprocess, sys

with open("${PRODUCTS_FILE}") as f:
    products = json.load(f)

sql_parts = []
for p in products:
    langs  = json.dumps(p.get("languages", []), ensure_ascii=False).replace("'", "''")
    images = json.dumps(p.get("images", []),    ensure_ascii=False).replace("'", "''")
    tags   = json.dumps(p.get("tags", []),      ensure_ascii=False).replace("'", "''")
    attrs  = json.dumps(p.get("attributes", {}),ensure_ascii=False).replace("'", "''")
    name        = p["name"].replace("'", "''")
    slug        = p["slug"].replace("'", "''")
    description = p.get("description","").replace("'","''")
    short_desc  = p.get("short_description","").replace("'","''")
    sql_parts.append(f"""
INSERT INTO ${TENANT_SCHEMA}.products
  (id, name, slug, category, description, short_description,
   base_price, currency, duration_minutes, max_pax, min_pax,
   languages, images, tags, attributes, is_active)
VALUES (
  '{p["id"]}', '{name}', '{slug}', '{p.get("category","")}',
  '{description}', '{short_desc}',
  {p["base_price"]}, '{p["currency"]}',
  {p.get("duration_minutes") or "NULL"},
  {p.get("max_pax") or "NULL"}, {p.get("min_pax", 1)},
  '{langs}'::jsonb, '{images}'::jsonb, '{tags}'::jsonb, '{attrs}'::jsonb,
  {str(p.get("is_active", True)).lower()}
)
ON CONFLICT (id) DO UPDATE SET
  name=EXCLUDED.name, category=EXCLUDED.category,
  description=EXCLUDED.description, base_price=EXCLUDED.base_price,
  duration_minutes=EXCLUDED.duration_minutes, max_pax=EXCLUDED.max_pax,
  languages=EXCLUDED.languages, images=EXCLUDED.images,
  tags=EXCLUDED.tags, attributes=EXCLUDED.attributes,
  is_active=EXCLUDED.is_active, updated_at=now();
""".strip())

full_sql = "\n".join(sql_parts)
result = subprocess.run(
    ["docker", "exec", "-i", "nia_postgres", "psql", "-U", "nia_user", "-d", "nia_dev"],
    input=full_sql.encode(), capture_output=True
)
if result.returncode != 0:
    print("ERROR seeding products:", result.stderr.decode(), file=sys.stderr)
    sys.exit(1)
print(f"  {len(products)} products inserted/updated")
PYEOF

success "Products seeded: ${PRODUCT_COUNT} products into ${TENANT_SCHEMA}"

# ── 5. Create / upsert moda_imagen tenant (StyleSense) ───────────
MODA_FILE="data/seed/tenants/moda_imagen.json"
MODA_TENANT_ID="moda_imagen"
MODA_COLLECTION="moda_imagen_docs"

info "Creating moda_imagen tenant (StyleSense)..."

MODA_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  "${TENANT_MANAGER_URL}/api/tenants/${MODA_TENANT_ID}")

if [ "$MODA_STATUS" -eq 200 ]; then
  warn "Tenant '${MODA_TENANT_ID}' already exists — skipping creation"
else
  MODA_RESP=$(curl -sf -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d @"$MODA_FILE" \
    "${TENANT_MANAGER_URL}/api/tenants")
  success "Tenant created: $(echo "$MODA_RESP" | jq -r '.data.id // "moda_imagen"')"
fi

# ── 6. Apply Telegram config to moda_imagen (same bot as demo_turismo) ──
info "Enabling Telegram channel on moda_imagen..."

# Read bot_token and webhook_secret from demo_turismo Redis config
DEMO_BOT_TOKEN=$(docker exec nia_redis redis-cli GET "tenant:demo_turismo:config" \
  | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('telegram_config',{}).get('bot_token',''))")
DEMO_WEBHOOK_SECRET=$(docker exec nia_redis redis-cli GET "tenant:demo_turismo:config" \
  | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('telegram_config',{}).get('webhook_secret',''))")
DEMO_BOT_USERNAME=$(docker exec nia_redis redis-cli GET "tenant:demo_turismo:config" \
  | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('telegram_config',{}).get('bot_username',''))")

if [ -n "$DEMO_BOT_TOKEN" ]; then
  MODA_TELEGRAM_PATCH=$(cat <<JSONPATCH
{
  "telegram_config": {
    "enabled": true,
    "bot_token": "${DEMO_BOT_TOKEN}",
    "bot_username": "${DEMO_BOT_USERNAME}",
    "webhook_secret": "${DEMO_WEBHOOK_SECRET}",
    "allowed_chat_ids": [],
    "welcome_message": "¡Hola! 👗 Soy StyleSense, tu asesora de imagen personal. ¿Qué look estás buscando hoy?",
    "parse_mode": "Markdown"
  }
}
JSONPATCH
)
  curl -sf -X PATCH \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "$MODA_TELEGRAM_PATCH" \
    "${TENANT_MANAGER_URL}/api/tenants/${MODA_TENANT_ID}/config" > /dev/null \
    && success "Telegram enabled on moda_imagen (shared bot: @${DEMO_BOT_USERNAME})" \
    || warn "Could not patch moda_imagen Telegram config via API — updating Redis directly"
else
  warn "demo_turismo bot_token not found — skipping Telegram config for moda_imagen"
  warn "Run ./scripts/seed.sh after configuring Telegram on demo_turismo"
fi

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
