#!/bin/bash

# Script para generar colección de Postman automáticamente desde OpenAPI specs

set -e

echo "🚀 Generando colección de Postman desde OpenAPI specs..."

# Crear directorio para las specs
mkdir -p .postman/openapi

# URLs de los servicios (ajusta según tu entorno)
BASE_URL=${BASE_URL:-"http://localhost"}

declare -A SERVICES=(
    ["orchestrator"]="8001"
    ["rag-service"]="8002"
    ["tenant-manager"]="8003"
    ["recommender"]="8004"
    ["model-adapter"]="8005"
    ["checkout"]="8006"
    ["handoff"]="8007"
    ["transcript"]="8008"
    ["fallback"]="8009"
)

# Descargar specs OpenAPI de cada servicio
echo "📥 Descargando especificaciones OpenAPI..."
for service in "${!SERVICES[@]}"; do
    port=${SERVICES[$service]}
    echo "  → $service ($BASE_URL:$port)"
    
    # Intentar descargar la spec OpenAPI
    curl -s "$BASE_URL:$port/openapi.json" > ".postman/openapi/$service.json" 2>/dev/null || {
        echo "    ⚠️  Servicio $service no disponible en puerto $port"
    }
done

# Instalar newman y openapi-to-postman si no están disponibles
if ! command -v newman &> /dev/null; then
    echo "📦 Instalando newman..."
    npm install -g newman
fi

if ! command -v openapi2postmanv2 &> /dev/null; then
    echo "📦 Instalando openapi-to-postman..."
    npm install -g openapi-to-postman
fi

# Convertir cada OpenAPI spec a colección Postman
echo "🔄 Convirtiendo OpenAPI specs a colecciones Postman..."
mkdir -p .postman/collections

for spec_file in .postman/openapi/*.json; do
    if [ -f "$spec_file" ]; then
        service_name=$(basename "$spec_file" .json)
        echo "  → Procesando $service_name..."
        
        # Convertir OpenAPI a Postman
        openapi2postmanv2 -s "$spec_file" -o ".postman/collections/$service_name.json" \
            --pretty \
            --options-short
    fi
done

# Combinar todas las colecciones en una sola
echo "🔗 Combinando colecciones..."
node scripts/merge-postman-collections.js

echo "✅ Colección de Postman generada en: .postman/NIA-Complete-Collection.json"
echo "📋 Para importar en Postman:"
echo "   1. Abre Postman"
echo "   2. Import → .postman/NIA-Complete-Collection.json"
echo "   3. Import → NIA-Environment-Development.json"

# Ejecutar tests automáticamente (opcional)
if [ "$RUN_TESTS" = "true" ]; then
    echo "🧪 Ejecutando tests de la colección..."
    newman run .postman/NIA-Complete-Collection.json \
        -e NIA-Environment-Development.json \
        --reporters cli,html \
        --reporter-html-export .postman/test-results.html
fi