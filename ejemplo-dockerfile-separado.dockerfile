# Dockerfile para repo independiente (tenant-manager)
FROM python:3.12-slim as base

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────────
# Opción A: Si usas git submodule para shared
# ─────────────────────────────────────────────────────────────────
# COPY shared /app/shared
# RUN pip install -e /app/shared

# ─────────────────────────────────────────────────────────────────  
# Opción B: Si usas PyPI package para shared
# ─────────────────────────────────────────────────────────────────
ARG SHARED_VERSION=1.2.3
RUN pip install --no-cache-dir nia-shared==$SHARED_VERSION

# Instalar dependencias del servicio
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del servicio
COPY . .

EXPOSE 8003

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]