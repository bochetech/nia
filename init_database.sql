-- Script de inicialización completo de la base de datos
-- Ejecuta todas las migraciones: 0001 + 0002 + 0003

-- ======================================================================
-- Migración 0001: Schema inicial
-- ======================================================================

-- Tabla de alembic version (para tracking de migraciones)
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);

-- Tabla de tenants principal en schema public
CREATE TABLE IF NOT EXISTS tenants (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    plan VARCHAR(32) NOT NULL DEFAULT 'starter',
    schema_name VARCHAR(64) NOT NULL UNIQUE,
    api_key_hash VARCHAR(128) NOT NULL UNIQUE,
    branding JSONB NOT NULL DEFAULT '{"primary_color":"#2563eb","logo_url":null,"welcome_message":"¡Hola! Soy NIA.","placeholder":"Escribe un mensaje…"}',
    qdrant_collection VARCHAR(128),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tabla de leads (capturas de email)
CREATE TABLE IF NOT EXISTS leads (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id),
    email VARCHAR(320) NOT NULL,
    full_name VARCHAR(255),
    phone VARCHAR(32),
    message TEXT,
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    utm_source VARCHAR(128),
    utm_medium VARCHAR(128),
    utm_campaign VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ======================================================================
-- Migración 0002: Booking intents 
-- ======================================================================

-- Agrega campos GDPR y source a leads
ALTER TABLE leads 
ADD COLUMN IF NOT EXISTS gdpr_consent BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS source VARCHAR(64) DEFAULT 'widget';

-- ======================================================================
-- Migración 0003: Configuraciones avanzadas 🆕
-- ======================================================================

-- Actualizar tabla tenants con nuevas configuraciones
ALTER TABLE tenants 
ADD COLUMN IF NOT EXISTS slug VARCHAR(50) UNIQUE,
ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'provisioning',
ADD COLUMN IF NOT EXISTS db_schema VARCHAR(60),
ADD COLUMN IF NOT EXISTS contact_email VARCHAR(200),
ADD COLUMN IF NOT EXISTS jwt_secret VARCHAR(64),
ADD COLUMN IF NOT EXISTS ui_config JSONB NOT NULL DEFAULT '{}',
ADD COLUMN IF NOT EXISTS lead_config JSONB NOT NULL DEFAULT '{}',
ADD COLUMN IF NOT EXISTS limits_config JSONB NOT NULL DEFAULT '{}',
ADD COLUMN IF NOT EXISTS rag_config JSONB NOT NULL DEFAULT '{}',
ADD COLUMN IF NOT EXISTS teams_config JSONB NOT NULL DEFAULT '{}',
ADD COLUMN IF NOT EXISTS email_config JSONB NOT NULL DEFAULT '{}',
ADD COLUMN IF NOT EXISTS ai_config JSONB NOT NULL DEFAULT '{}',
ADD COLUMN IF NOT EXISTS fsm_config JSONB NOT NULL DEFAULT '{}',
ADD COLUMN IF NOT EXISTS payment_config JSONB NOT NULL DEFAULT '{}',
ADD COLUMN IF NOT EXISTS config_version INTEGER DEFAULT 1;

-- Actualizar campos existentes para compatibilidad
UPDATE tenants SET slug = id WHERE slug IS NULL;
UPDATE tenants SET db_schema = 'tenant_' || id WHERE db_schema IS NULL;
UPDATE tenants SET status = 'active' WHERE status = 'provisioning' AND is_active = true;

-- Tabla de API keys adicionales por tenant
CREATE TABLE IF NOT EXISTS tenant_api_keys (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    key_hash VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tenant_api_keys_tenant_id ON tenant_api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_leads_tenant_id ON leads(tenant_id);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at);

-- ======================================================================
-- Marcar las migraciones como aplicadas
-- ======================================================================

-- Insertar versión final de migración
INSERT INTO alembic_version (version_num) VALUES ('0003') 
ON CONFLICT (version_num) DO NOTHING;

-- ======================================================================
-- Datos de prueba (opcional)
-- ======================================================================

-- Insertar tenant demo si no existe
INSERT INTO tenants (
    id, 
    name, 
    slug,
    plan, 
    schema_name, 
    db_schema,
    api_key_hash, 
    contact_email,
    jwt_secret,
    status,
    branding,
    ui_config,
    lead_config,
    rag_config,
    qdrant_collection
) VALUES (
    'demo-tenant',
    'Demo Tenant',
    'demo-tenant', 
    'pro',
    'tenant_demo_tenant',
    'tenant_demo_tenant',
    '$2b$12$dummy.hash.for.demo.tenant.only',
    'admin@demo-tenant.com',
    'demo_jwt_secret_change_in_production',
    'active',
    '{"primary_color":"#0f766e","logo_url":null,"welcome_message":"¡Hola! Soy NIA, tu asistente de viajes. ¿A dónde quieres escaparte?","placeholder":"Ej: Quiero un tour de 3 días en la costa…"}',
    '{"primary_color":"#0f766e","secondary_color":"#f0fdfa","logo_url":null,"company_name":"Demo Travel"}',
    '{"enabled":true,"required_fields":["email","name"],"optional_fields":["phone","message"],"gdpr_enabled":true}',
    '{"confidence_threshold":0.65,"max_tokens_response":500,"top_k_retrieval":8}',
    'nia_tenant_demo_tenant_knowledge'
) ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE tenants IS 'Tabla principal de tenants con todas las configuraciones';
COMMENT ON COLUMN tenants.teams_config IS 'Configuración de integración Microsoft Teams';
COMMENT ON COLUMN tenants.email_config IS 'Configuración SMTP para envío de emails';  
COMMENT ON COLUMN tenants.ai_config IS 'Configuración de modelos de IA y prompts';
COMMENT ON COLUMN tenants.fsm_config IS 'Configuración de máquina de estados conversacional';
COMMENT ON COLUMN tenants.payment_config IS 'Configuración de checkout y pagos';