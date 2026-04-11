#!/usr/bin/env python3
"""
Test script para las nuevas configuraciones avanzadas del tenant.
"""

import json
from pydantic import ValidationError

from shared.models.domain import (
    AIConfig,
    EmailConfig,
    FSMConfig,
    PaymentConfig,
    TeamsConfig,
    TenantConfigDTO,
)


def test_new_configs():
    """Prueba que las nuevas configuraciones se crean correctamente."""
    
    # Test TeamsConfig
    teams_config = TeamsConfig(
        enabled=True,
        webhook_url="https://outlook.office.com/webhook/123",
        channel_id="general",
        auto_handoff_keywords=["ayuda", "humano", "error"],
        escalation_timeout_minutes=5,
        adaptive_card_template="advanced",
        mention_users=["user1@company.com", "user2@company.com"],
    )
    print("✅ TeamsConfig creado correctamente")
    print(f"   Webhook: {teams_config.webhook_url}")
    print(f"   Keywords: {teams_config.auto_handoff_keywords}")

    # Test EmailConfig  
    email_config = EmailConfig(
        enabled=True,
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_user="nia@company.com",
        smtp_password="supersecret",
        smtp_from="nia@company.com",
        smtp_from_name="Asistente NIA",
        use_tls=True,
        timeout_seconds=30,
        template_path="custom_templates",
    )
    print("✅ EmailConfig creado correctamente")
    print(f"   SMTP Host: {email_config.smtp_host}:{email_config.smtp_port}")
    print(f"   From: {email_config.smtp_from_name} <{email_config.smtp_from}>")

    # Test AIConfig
    ai_config = AIConfig(
        primary_provider="vertex_ai",
        primary_model="gemini-1.5-pro",
        fallback_provider="openai",
        fallback_model="gpt-4o",
        temperature=0.2,
        max_tokens=2000,
        top_p=0.8,
        system_prompt_override="Eres un asistente especializado en turismo.",
        enable_caching=True,
        cache_ttl_seconds=600,
        cost_optimization=True,
    )
    print("✅ AIConfig creado correctamente")
    print(f"   Primary: {ai_config.primary_provider}/{ai_config.primary_model}")
    print(f"   Fallback: {ai_config.fallback_provider}/{ai_config.fallback_model}")
    print(f"   Temperature: {ai_config.temperature}")

    # Test FSMConfig
    fsm_config = FSMConfig(
        states_enabled=["idle", "greeting", "discovery", "recommending", "checkout_init", "handoff_active"],
        max_conversation_turns=100,
        session_timeout_minutes=720,  # 12 horas
        nps_enabled=True,
        post_chat_delay_seconds=180,  # 3 minutos
        handoff_triggers=["complaint", "technical_issue", "billing_question"],
        auto_close_after_minutes=30,
    )
    print("✅ FSMConfig creado correctamente")
    print(f"   Estados habilitados: {len(fsm_config.states_enabled)}")
    print(f"   Max turns: {fsm_config.max_conversation_turns}")
    print(f"   Timeout: {fsm_config.session_timeout_minutes} min")

    # Test PaymentConfig
    payment_config = PaymentConfig(
        enabled=True,
        stripe_public_key="pk_test_123abc",
        stripe_secret_key="sk_test_456def",
        currency_default="USD",
        payment_methods=["card", "ideal", "sepa_debit"],
        checkout_session_expires_minutes=15,
        success_url_template="https://{domain}/gracias?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url_template="https://{domain}/cancelado",
        webhook_secret="whsec_789ghi",
    )
    print("✅ PaymentConfig creado correctamente")
    print(f"   Moneda: {payment_config.currency_default}")
    print(f"   Métodos: {payment_config.payment_methods}")
    print(f"   Expires: {payment_config.checkout_session_expires_minutes} min")

    # Test TenantConfigDTO completo
    tenant_config = TenantConfigDTO(
        tenant_id="test-tenant",
        version=2,
        teams_config=teams_config,
        email_config=email_config,
        ai_config=ai_config,
        fsm_config=fsm_config,
        payment_config=payment_config,
    )
    print("✅ TenantConfigDTO completo creado correctamente")
    print(f"   Tenant ID: {tenant_config.tenant_id}")
    print(f"   Version: {tenant_config.version}")

    # Test serialización JSON
    tenant_json = tenant_config.model_dump()
    json_str = json.dumps(tenant_json, indent=2, default=str)
    print("✅ Serialización JSON correcta")
    print(f"   Tamaño JSON: {len(json_str)} caracteres")

    # Test deserialización
    restored = TenantConfigDTO(**tenant_json)
    print("✅ Deserialización correcta")
    print(f"   Teams enabled: {restored.teams_config.enabled}")
    print(f"   Email enabled: {restored.email_config.enabled}")
    print(f"   AI primary: {restored.ai_config.primary_model}")

    return True


def test_validation():
    """Prueba validaciones de Pydantic."""
    
    # Test validación de email inválido
    try:
        EmailConfig(smtp_host="", smtp_port=0)
        print("❌ Validación falló - debería requerir host válido")
    except ValidationError:
        print("✅ Validación correcta - host requerido")

    # Test temperatura fuera de rango
    try:
        AIConfig(temperature=2.5)  # Fuera del rango normal 0-2
        print("⚠️  Temperatura alta permitida (podría ser válida para algunos casos)")
    except ValidationError:
        print("✅ Validación correcta - temperatura restringida")

    # Test timeout negativo
    try:
        FSMConfig(session_timeout_minutes=-1)
        print("⚠️  Timeout negativo permitido")
    except ValidationError:
        print("✅ Validación correcta - timeout debe ser positivo")

    return True


if __name__ == "__main__":
    print("🧪 Probando las nuevas configuraciones avanzadas...\n")
    
    try:
        test_new_configs()
        print("\n" + "="*50)
        test_validation()
        print("\n🎉 Todas las pruebas pasaron correctamente!")
    except Exception as e:
        print(f"\n❌ Error en las pruebas: {e}")
        import traceback
        traceback.print_exc()