#!/usr/bin/env python3
"""Genera un admin JWT token para uso en scripts de seed/desarrollo."""
import sys
import os
import uuid
from datetime import UTC, datetime, timedelta

# Leer JWT_SECRET del .env o del argumento
def load_env(env_file=".env"):
    env = {}
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env

env = load_env()
JWT_SECRET = os.environ.get("JWT_SECRET") or env.get("JWT_SECRET") or "dev-jwt-secret-change-in-prod"

try:
    from jose import jwt
except ImportError:
    print("ERROR: python-jose not installed. Run: pip install python-jose", file=sys.stderr)
    sys.exit(1)

now = datetime.now(UTC)
claims = {
    "sub": "seed-script",
    "tid": "system",
    "role": "super_admin",
    "iss": "nia-tenant-manager",
    "aud": "nia-api",
    "iat": now,
    "exp": now + timedelta(hours=1),
    "jti": str(uuid.uuid4()),
}

token = jwt.encode(claims, JWT_SECRET, algorithm="HS256")
print(token)
