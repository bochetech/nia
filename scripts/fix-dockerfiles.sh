#!/bin/bash

# Script para arreglar los Dockerfiles para que funcionen correctamente
# con la estructura de carpetas compartidas

echo "🔧 Arreglando Dockerfiles para usar shared correctamente..."

# Lista de servicios
services=(
  "orchestrator"
  "rag-service"
  "tenant-manager"
  "recommender"
  "model-adapter"
  "checkout"
  "handoff"
  "transcript"
  "fallback"
)

for service in "${services[@]}"; do
  dockerfile="services/$service/Dockerfile.dev"
  
  if [ -f "$dockerfile" ]; then
    echo "📝 Arreglando $service..."
    
    # Crear backup
    cp "$dockerfile" "$dockerfile.bak"
    
    # Arreglar rutas en Dockerfile
    sed -i '' 's|COPY ../../shared|COPY shared|g' "$dockerfile"
    sed -i '' 's|COPY requirements.txt|COPY services/'$service'/requirements.txt|g' "$dockerfile"
    sed -i '' 's|COPY \. \.|COPY services/'$service'/ .|g' "$dockerfile"
    
    echo "  ✅ $service Dockerfile actualizado"
  else
    echo "  ⚠️  $dockerfile no encontrado"
  fi
done

echo ""
echo "🐳 Actualizando docker-compose.yml..."

# Crear backup del docker-compose.yml
cp docker-compose.yml docker-compose.yml.bak

# Arreglar contextos de build en docker-compose.yml
for service in "${services[@]}"; do
  # Cambiar el contexto de ./services/$service a .
  # y agregar dockerfile: ./services/$service/Dockerfile.dev
  sed -i '' "/build:/,/dockerfile:/ {
    s|context: ./services/$service|context: .|
    s|dockerfile: Dockerfile.dev|dockerfile: ./services/$service/Dockerfile.dev|
  }" docker-compose.yml
done

# También arreglar migrations
sed -i '' "/migrations:/,/dockerfile:/ {
  s|context: ./services/tenant-manager|context: .|
  s|dockerfile: Dockerfile.dev|dockerfile: ./services/tenant-manager/Dockerfile.dev|
}" docker-compose.yml

echo "  ✅ docker-compose.yml actualizado"
echo ""
echo "🎉 Todos los archivos han sido arreglados!"
echo "📋 Ahora puedes ejecutar: make dev"