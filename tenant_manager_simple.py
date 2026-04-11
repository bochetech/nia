#!/usr/bin/env python3
"""
Servidor FastAPI simplificado para probar los endpoints de configuración.
Usa psycopg2 directamente en lugar de SQLAlchemy async.
"""

import json
from typing import Union
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(
    title="NIA Tenant Manager",
    description="Multi-tenant configuration API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de BD
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "nia_dev",
    "user": "nia_user",
    "password": "nia_secret"
}

# Modelos Pydantic simplificados
class TeamsConfig(BaseModel):
    enabled: bool = False
    webhook_url: str = ""
    channel_id: str = "general"
    auto_handoff_keywords: list[str] = ["queja", "problema", "reclamo"]
    escalation_timeout_minutes: int = 10
    adaptive_card_template: str = "default"
    mention_users: list[str] = []

class EmailConfig(BaseModel):
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@nia-platform.com"
    smtp_from_name: str = "Asistente NIA"
    use_tls: bool = True
    timeout_seconds: int = 30
    template_path: str = "default"

class AIConfig(BaseModel):
    primary_provider: str = "vertex_ai"
    primary_model: str = "gemini-1.5-flash"
    fallback_provider: str = "openai"
    fallback_model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 1000
    top_p: float = 0.9
    system_prompt_override: str = ""
    enable_caching: bool = True
    cache_ttl_seconds: int = 300
    cost_optimization: bool = True

class FSMConfig(BaseModel):
    states_enabled: list[str] = ["idle", "greeting", "discovery", "recommending", "checkout_init"]
    max_conversation_turns: int = 50
    session_timeout_minutes: int = 480
    nps_enabled: bool = True
    post_chat_delay_seconds: int = 300
    handoff_triggers: list[str] = ["complaint", "unresolved", "explicit_request"]
    auto_close_after_minutes: int = 60

class PaymentConfig(BaseModel):
    enabled: bool = False
    stripe_public_key: str = ""
    stripe_secret_key: str = ""
    currency_default: str = "CLP"
    payment_methods: list[str] = ["card"]
    checkout_session_expires_minutes: int = 30
    success_url_template: str = "https://{domain}/payment/success"
    cancel_url_template: str = "https://{domain}/payment/cancel"
    webhook_secret: str = ""

class RAGConfig(BaseModel):
    """Configuración del sistema RAG (Retrieval Augmented Generation)"""
    confidence_threshold: float = 0.65
    max_tokens_response: int = 500
    fallback_message: str = "No tengo información precisa sobre eso. ¿Te gustaría hablar con un asesor?"
    top_k_retrieval: int = 8
    top_k_rerank: int = 3

class TenantResponse(BaseModel):
    id: str
    name: str
    status: str
    config_version: int
    teams_config: dict
    email_config: dict
    ai_config: dict
    fsm_config: dict
    payment_config: dict
    rag_config: dict

# Funciones de BD
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def get_tenant(tenant_id: str):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, name, status, config_version,
                       teams_config, email_config, ai_config, fsm_config, payment_config, rag_config
                FROM tenants WHERE id = %s
            """, (tenant_id,))
            return cursor.fetchone()

def update_tenant_config(tenant_id: str, config_field: str, config_data: dict):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                UPDATE tenants 
                SET {config_field} = %s, config_version = config_version + 1
                WHERE id = %s
                RETURNING config_version
            """, (json.dumps(config_data), tenant_id))
            result = cursor.fetchone()
            conn.commit()
            return result['config_version'] if result else None

# Endpoints REST

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "nia-tenant-manager"}

@app.get("/api/tenants/{tenant_id}")
async def get_tenant_info(tenant_id: str):
    """Obtener información del tenant."""
    tenant = get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    
    return {"data": dict(tenant)}

@app.get("/api/tenants/{tenant_id}/config")
async def get_tenant_config(tenant_id: str):
    """Obtener todas las configuraciones del tenant."""
    tenant = get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    
    config = {
        "tenant_id": tenant["id"],
        "version": tenant["config_version"],
        "teams_config": tenant["teams_config"] or {},
        "email_config": tenant["email_config"] or {},
        "ai_config": tenant["ai_config"] or {},
        "fsm_config": tenant["fsm_config"] or {},
        "payment_config": tenant["payment_config"] or {},
    }
    
    return {"data": config}

@app.patch("/api/tenants/{tenant_id}/teams-config")
async def update_teams_config(tenant_id: str, config: TeamsConfig):
    """Actualizar configuración específica de Microsoft Teams."""
    tenant = get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    
    new_version = update_tenant_config(tenant_id, "teams_config", config.model_dump())
    
    return {
        "data": {
            "message": "Teams configuration updated successfully",
            "tenant_id": tenant_id,
            "config_version": new_version,
            "teams_config": config.model_dump()
        }
    }

@app.patch("/api/tenants/{tenant_id}/email-config")
async def update_email_config(tenant_id: str, config: EmailConfig):
    """Actualizar configuración SMTP para envío de emails."""
    tenant = get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    
    new_version = update_tenant_config(tenant_id, "email_config", config.model_dump())
    
    return {
        "data": {
            "message": "Email configuration updated successfully", 
            "tenant_id": tenant_id,
            "config_version": new_version,
            "email_config": config.model_dump()
        }
    }

@app.patch("/api/tenants/{tenant_id}/ai-config")
async def update_ai_config(tenant_id: str, config: AIConfig):
    """Actualizar configuración de modelos de IA y prompts."""
    tenant = get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    
    new_version = update_tenant_config(tenant_id, "ai_config", config.model_dump())
    
    return {
        "data": {
            "message": "AI configuration updated successfully",
            "tenant_id": tenant_id, 
            "config_version": new_version,
            "ai_config": config.model_dump()
        }
    }

@app.patch("/api/tenants/{tenant_id}/fsm-config")
async def update_fsm_config(tenant_id: str, config: FSMConfig):
    """Actualizar configuración avanzada de la máquina de estados."""
    tenant = get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    
    new_version = update_tenant_config(tenant_id, "fsm_config", config.model_dump())
    
    return {
        "data": {
            "message": "FSM configuration updated successfully",
            "tenant_id": tenant_id,
            "config_version": new_version, 
            "fsm_config": config.model_dump()
        }
    }

@app.patch("/api/tenants/{tenant_id}/payment-config")
async def update_payment_config(tenant_id: str, config: PaymentConfig):
    """Actualizar configuración de checkout y pagos."""
    tenant = get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    
    new_version = update_tenant_config(tenant_id, "payment_config", config.model_dump())
    
    return {
        "data": {
            "message": "Payment configuration updated successfully",
            "tenant_id": tenant_id,
            "config_version": new_version,
            "payment_config": config.model_dump()
        }
    }

@app.patch("/api/tenants/{tenant_id}/rag-config")
async def update_rag_config(tenant_id: str, config: RAGConfig):
    """Actualizar configuración del sistema RAG (Retrieval Augmented Generation)."""
    tenant = get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    
    new_version = update_tenant_config(tenant_id, "rag_config", config.model_dump())
    
    return {
        "data": {
            "message": "RAG configuration updated successfully",
            "tenant_id": tenant_id,
            "config_version": new_version,
            "rag_config": config.model_dump()
        }
    }

if __name__ == "__main__":
    print("🚀 Iniciando Tenant Manager simplificado...")
    print("📖 Documentación disponible en:")
    print("   🌐 http://localhost:8003/docs (Swagger UI)")
    print("   🌐 http://localhost:8003/redoc (ReDoc)")
    
    uvicorn.run(app, host="0.0.0.0", port=8003)