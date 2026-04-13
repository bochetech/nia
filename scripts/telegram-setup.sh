#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# scripts/telegram-setup.sh
#
# Levanta cloudflared, extrae la URL pública del tunnel y registra
# el webhook de Telegram automáticamente.
#
# Uso:
#   ./scripts/telegram-setup.sh [tenant_id]
#
# Requiere:
#   - docker compose up -d telegram-gateway  (ya corriendo)
#   - TENANT_MANAGER corriendo en localhost:8003
# ─────────────────────────────────────────────────────────────────

set -euo pipefail

TENANT_ID="${1:-demo_turismo}"
TENANT_MANAGER_URL="http://localhost:8003"
GATEWAY_URL="http://localhost:8010"
MAX_WAIT=30

echo "🚇 Iniciando cloudflared tunnel..."
docker compose --profile dev up -d cloudflared 2>/dev/null

echo "⏳ Esperando URL pública del tunnel (max ${MAX_WAIT}s)..."
PUBLIC_URL=""
for i in $(seq 1 $MAX_WAIT); do
    PUBLIC_URL=$(docker compose logs cloudflared 2>/dev/null \
        | grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' \
        | tail -1)
    if [ -n "$PUBLIC_URL" ]; then
        break
    fi
    sleep 1
done

if [ -z "$PUBLIC_URL" ]; then
    echo "❌ No se pudo obtener la URL del tunnel después de ${MAX_WAIT}s"
    echo "   Revisa los logs: docker compose logs cloudflared"
    exit 1
fi

echo "✅ Tunnel activo: $PUBLIC_URL"

# Obtener token admin
echo "🔑 Obteniendo token admin..."
TOKEN=$(curl -sf -X POST "${TENANT_MANAGER_URL}/auth/token" \
    -H 'Content-Type: application/json' \
    -d '{"email":"admin@nia.local","password":"changeme"}' \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

if [ -z "$TOKEN" ]; then
    echo "❌ No se pudo obtener el token admin. ¿Está corriendo el tenant-manager?"
    exit 1
fi

# Registrar webhook
echo "📡 Registrando webhook en Telegram para tenant '${TENANT_ID}'..."
RESPONSE=$(curl -sf -X POST "${GATEWAY_URL}/setup/${TENANT_ID}" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${TOKEN}" \
    -d "{\"public_url\": \"${PUBLIC_URL}\"}")

echo "✅ Webhook registrado:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

echo ""
echo "🤖 Bot activo. Escribe al bot en Telegram."
echo "   Tunnel URL: $PUBLIC_URL"
echo "   Para detener: docker compose --profile dev stop cloudflared"
