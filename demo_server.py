"""
demo_server.py — Mini servidor para la demo del widget NIA.

Expone:
  GET  /              → sirve demo.html
  GET  /static/*      → archivos estáticos (widget JS)
  POST /v1/chat       → proxy al model-adapter (model-adapter en :8005)
  POST /v1/sessions/* → no-op (lead capture — solo para la demo)
  GET  /tenants/*/widget-config → config de branding hardcodeada

Uso:
  python demo_server.py

Luego abre: http://localhost:8088
"""

import asyncio
import json
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# ── Config ────────────────────────────────────────────────────────────────────

MODEL_ADAPTER_URL = os.getenv("MODEL_ADAPTER_URL", "http://127.0.0.1:8005")
DEMO_PORT         = int(os.getenv("DEMO_PORT", "8088"))
ROOT              = Path(__file__).parent

SYSTEM_PROMPT = """Eres NIA, asistente de enoturismo del Centro del Vino Concha y Toro.
Ayudas a los visitantes a conocer y reservar experiencias en el centro ubicado en Pirque, Chile (≈1 hora de Santiago).
Responde siempre en español, de forma amigable y concisa (máximo 4 oraciones por respuesta).
Si no conoces el precio exacto, invita al visitante a contactar directamente al centro.

ACTIVIDADES DISPONIBLES:
• Visita Guiada Premium (2h) — Horarios: 09:10, 09:40, 10:10, 10:50, 12:00 (+8 más) | Extras: Menú Almuerzo Bodega 1883; Degustación Elixir Casillero del Diablo
• Visita Guiada Premium + Tasting The New Wines (2h 45min) — Horarios: 12:55, 14:30, 21:00 | Lujo y ocasiones especiales
• Visita Guiada Premium + Tasting y Maridaje Terrunyo (2h 45min) — Horarios: 11:50, 12:50 | Maridaje gourmet
• Visita Guiada Premium + Tasting Cellar Collection (2h 45min) — Horarios: 10:00, 13:10, 14:50, 21:00 | Colección de autor
• Experiencia Nocturna Casillero del Diablo + Cena (3h) — Horarios: 18:30, 19:00, 19:50, 20:20, 20:50, 21:00 | Cena y maridaje
• Experiencia Nocturna Casillero del Diablo + Maridaje La Gran Barra (3h) — Horarios: 18:00, 18:30, 19:00, 19:50, 20:20, 21:00
• Visita Guiada Standard (1h 10min) — Horarios: 08:40, 08:50, 09:05, 09:20 (+10 más) | Opción económica
• Visita Guiada Premium + Tasting Marqués de Casa Concha (2h 45min) — Horarios: 09:30, 09:50, 10:20, 10:40 (+7 más)
• Visita Guiada Premium + Almuerzo Bodega 1883 (1h 40min) — Horarios: 11:10, 12:30 | Gastronomía
• Visita Guiada Casa Don Melchor y Parque Histórico + Tasting Amelia (2h) — Horario: 16:10 | Lujo, tasting 5 copas
• Experiencia Vendimia Concha y Toro 2026 (3h) — Horario: 12:00 | Temporada vendimia
• Tiny Wine Concerts II (3h) — Horario: 19:00 | Conciertos con vino
• Tiny Wine Concerts II + Cena (3h) — Horario: 19:00 | Conciertos + cena
• Bodega 1883 - Almuerzo (1h) — Horarios: 12:30, 12:45, 13:00, 13:15 (+8 más) | Solo gastronomía
• Bodega 1883 - Cena (1h) — Horarios: 16:00, 16:15, 16:30 (+9 más)
• Bodega 1883 - Maridaje Terrunyo (1h) — Múltiples horarios desde 12:45
• Bodega 1883 - La Gran Barra (1h) — Múltiples horarios, amplia disponibilidad
• Experience The New Wines Shell and Bull (2h 45min) — Horarios: 12:55, 14:30 | Experiencia premium
• Experiencia Gastronómica Valentine's Day (2h) — Múltiples horarios | Ocasiones especiales
• Experiencia & Sabores de Semana Santa (3h) — Horarios: 10:30, 11:00, 12:45, 16:30
• Visita Guiada Premium Privada (2h) — Disponible bajo reserva | Grupos privados
• Visita Guiada Standard Privada (1h 10min) — Disponible bajo reserva
• Visita Guiada Premium + Tasting Marqués de Casa Concha Privada (2h 45min) — Privada
• Visita Guiada Premium + Tasting Cellar Collection Privada (2h 45min) — Privada
• Bodega 1883 - Almuerzo Semana Santa (3h) — Múltiples horarios

INFORMACIÓN GENERAL:
- Ubicación: Av. Virginia Subercaseaux 210, Pirque, Región Metropolitana, Chile
- Distancia desde Santiago: ≈1 hora en auto
- Rango de edades: La mayoría de tours permiten menores acompañados; consultar por experiencias nocturnas
- Reservas: A través del asistente NIA o contactando directamente al centro
"""

# ── Historial en memoria (por session_id) ─────────────────────────────────────
# Nota: en producción esto está en Redis + orchestrator
_sessions: dict[str, list[dict]] = {}

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="NIA Demo Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Middleware de seguridad — CSP, anti-clickjacking, MIME sniffing protection."""
    response = await call_next(request)
    
    # Content Security Policy — permite el widget embed + fuentes externas
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "font-src 'self' https: data:; "
        "img-src 'self' https: data:; "
        "connect-src 'self' https: http://localhost:* http://127.0.0.1:*; "
        "frame-ancestors 'self'"
    )
    
    # Prevenir MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Prevenir clickjacking
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    
    # Referrer policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Permissions policy (restrictivo)
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    
    return response

# ── Rutas estáticas ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_demo():
    return (ROOT / "demo.html").read_text()

@app.get("/docs", response_class=HTMLResponse)
async def serve_docs():
    return (ROOT / "packages/widget/docs/index.html").read_text()

@app.get("/packages/widget/dist/nia-widget.iife.js")
async def serve_widget():
    return FileResponse(ROOT / "packages/widget/dist/nia-widget.iife.js",
                        media_type="application/javascript")

# ── Tenant branding (mock) ────────────────────────────────────────────────────

@app.get("/tenants/{tenant_id}/widget-config")
async def widget_config(tenant_id: str):
    # El widget lee g.primary_color directamente (sin wrapper "data")
    return JSONResponse({
        "primary_color":   "#5c1a1a",
        "logo_url":        "https://conchaytoro.com/wp-content/themes/conchaytoro_wp/dist/assets/icons/cyt-logo.svg",
        "welcome_message": "¡Hola! Soy NIA 🍷 Tu asistente del Centro del Vino Concha y Toro. ¿En qué puedo ayudarte hoy?",
        "placeholder":     "Pregunta sobre nuestros tours y experiencias…",
        "widget_token":    "demo-token",
    })

# ── Chat proxy → model-adapter ────────────────────────────────────────────────

@app.post("/v1/chat")
async def chat(req: Request):
    body = await req.json()
    message: str = body.get("message", "")
    session_id: str = body.get("session_id", "default")

    # Mantener historial de la sesión
    history = _sessions.setdefault(session_id, [])
    history.append({"role": "user", "content": message})

    # Construir payload para el model-adapter
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{MODEL_ADAPTER_URL}/v1/chat/completions",
                json={"messages": messages},
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        return JSONResponse(
            {"detail": f"Model adapter error: {exc}"},
            status_code=502,
        )

    adapter_data = resp.json()
    assistant_reply: str = adapter_data["data"]["content"]

    # Guardar respuesta del asistente en historial
    history.append({"role": "assistant", "content": assistant_reply})

    # Limitar historial a últimas 20 vueltas
    if len(history) > 40:
        _sessions[session_id] = history[-40:]

    # Respuesta en el formato que espera el widget
    return JSONResponse({
        "data": {
            "session_id":         session_id,
            "response":           assistant_reply,
            "fsm_state":          "chatting",
            "show_lead_form":     False,
            "recommendations":    None,
            "handoff_triggered":  False,
            "checkout_url":       None,
        }
    })

# ── Lead capture (no-op en demo) ──────────────────────────────────────────────

@app.post("/v1/sessions/{session_id}/lead")
async def submit_lead(session_id: str, req: Request):
    body = await req.json()
    print(f"[DEMO] Lead capturado session={session_id}: {body}")
    return JSONResponse({"data": {"ok": True}})

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════╗
║        NIA Widget Demo Server v1.0               ║
╠══════════════════════════════════════════════════╣
║  URL:             http://localhost:{DEMO_PORT}          ║
║  Model adapter:   {MODEL_ADAPTER_URL}    ║
╚══════════════════════════════════════════════════╝
""")
    uvicorn.run(app, host="0.0.0.0", port=DEMO_PORT, log_level="warning")
