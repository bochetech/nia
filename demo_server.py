"""
demo_server.py — Reverse-proxy ligero para la demo del widget NIA.

Sirve la página demo.html y actúa como proxy transparente al stack real:
  GET  /                            → sirve demo.html
  GET  /packages/widget/dist/*      → widget JS compilado
  GET  /tenants/{id}/widget-config  → proxy → tenant-manager /api/tenants/{id}/widget-config
  POST /api/tenants/{id}/widget-token → proxy → tenant-manager
  POST /v1/chat                     → proxy → orchestrator
  POST /v1/sessions/{id}/lead       → proxy → orchestrator

NO tiene LLM propio, NO mantiene historial: todo pasa por el stack real
(orchestrator → RAG, recommender, model-adapter, etc.).

Uso:
  python demo_server.py

Luego abre: http://localhost:8088
"""

import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import uvicorn

# ── Config ────────────────────────────────────────────────────────────────────

ORCHESTRATOR_URL   = os.getenv("ORCHESTRATOR_URL",   "http://127.0.0.1:8001")
TENANT_MANAGER_URL = os.getenv("TENANT_MANAGER_URL", "http://127.0.0.1:8003")
DEMO_PORT          = int(os.getenv("DEMO_PORT", "8088"))
ROOT               = Path(__file__).parent

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="NIA Demo Server — Reverse Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Rutas estáticas ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_demo():
    return (ROOT / "demo.html").read_text()

@app.get("/docs/widget", response_class=HTMLResponse)
async def serve_docs():
    return (ROOT / "packages/widget/docs/index.html").read_text()

@app.get("/packages/widget/dist/nia-widget.iife.js")
async def serve_widget():
    return FileResponse(ROOT / "packages/widget/dist/nia-widget.iife.js",
                        media_type="application/javascript")


# ── Proxy: widget-config (widget llama /tenants/{id}/widget-config) ──────────
#    El widget NO pone /api en esta ruta, pero el tenant-manager sí,
#    así que reescribimos la ruta.

@app.get("/tenants/{tenant_id}/widget-config")
async def widget_config(tenant_id: str):
    """
    1. Obtiene la config de branding del tenant-manager real.
    2. Pide un widget-token JWT real (para que el widget se autentique
       contra el orchestrator).
    3. Inyecta el token en la respuesta para que el widget lo use.
    """
    async with httpx.AsyncClient(timeout=5) as client:
        # 1) Branding config
        try:
            cfg_resp = await client.get(
                f"{TENANT_MANAGER_URL}/api/tenants/{tenant_id}/widget-config"
            )
            cfg_resp.raise_for_status()
            config = cfg_resp.json()
        except Exception as exc:
            return JSONResponse(
                {"detail": f"tenant-manager /widget-config error: {exc}"},
                status_code=502,
            )

        # 2) Widget token (JWT real para autenticarse contra orchestrator)
        try:
            tok_resp = await client.post(
                f"{TENANT_MANAGER_URL}/api/tenants/{tenant_id}/widget-token",
                json={"page_url": "http://localhost:8088"},
            )
            tok_resp.raise_for_status()
            token_data = tok_resp.json().get("data", {})
            config["widget_token"] = token_data.get("token", "")
        except Exception:
            # Si falla el token, el widget arranca sin auth (limitado)
            config["widget_token"] = ""

    return JSONResponse(config)


# ── Proxy: widget-token (por si el widget lo pide directo) ───────────────────

@app.post("/api/tenants/{tenant_id}/widget-token")
async def proxy_widget_token(tenant_id: str, request: Request):
    body = await request.body()
    headers = {"Content-Type": "application/json"}
    auth = request.headers.get("Authorization")
    if auth:
        headers["Authorization"] = auth

    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.post(
            f"{TENANT_MANAGER_URL}/api/tenants/{tenant_id}/widget-token",
            content=body,
            headers=headers,
        )
    return JSONResponse(resp.json(), status_code=resp.status_code)


# ── Proxy: chat → orchestrator ───────────────────────────────────────────────

@app.post("/v1/chat")
async def proxy_chat(request: Request):
    """Reenvía el POST /v1/chat al orchestrator real."""
    body = await request.body()
    headers = {"Content-Type": "application/json"}
    auth = request.headers.get("Authorization")
    if auth:
        headers["Authorization"] = auth

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/v1/chat",
                content=body,
                headers=headers,
            )
        except httpx.ConnectError as exc:
            return JSONResponse(
                {"detail": f"Orchestrator no disponible: {exc}"},
                status_code=502,
            )

    return JSONResponse(resp.json(), status_code=resp.status_code)


# ── Proxy: lead capture → orchestrator ───────────────────────────────────────

@app.post("/v1/sessions/{session_id}/lead")
async def proxy_lead(session_id: str, request: Request):
    body = await request.body()
    headers = {"Content-Type": "application/json"}
    auth = request.headers.get("Authorization")
    if auth:
        headers["Authorization"] = auth

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/v1/sessions/{session_id}/lead",
                content=body,
                headers=headers,
            )
        except httpx.ConnectError:
            return JSONResponse({"data": {"ok": True}})

    return JSONResponse(resp.json(), status_code=resp.status_code)

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════╗
║    NIA Widget Demo — Reverse Proxy v2.0          ║
╠══════════════════════════════════════════════════╣
║  URL:            http://localhost:{DEMO_PORT}          ║
║  Orchestrator:   {ORCHESTRATOR_URL:<28s} ║
║  Tenant Manager: {TENANT_MANAGER_URL:<28s} ║
║                                                  ║
║  /v1/chat            → orchestrator (stack real) ║
║  /tenants/*/config   → tenant-manager            ║
╚══════════════════════════════════════════════════╝
""")
    uvicorn.run(app, host="0.0.0.0", port=DEMO_PORT, log_level="info")
