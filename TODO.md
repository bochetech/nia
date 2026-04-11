# 📋 OpenChat - Lista de Pendientes

*Última actualización: 11 de abril de 2026*

## 🎉 Completadas (5/10)

### ✅ 1. API Configuration Implementation
**Estado:** COMPLETADO  
**Descripción:** Implementados 5 sistemas de configuración completos por API: Teams, Email, AI, FSM, Payment. Todos los endpoints PATCH funcionando correctamente.

**Detalles:**
- `PATCH /api/tenants/{id}/teams-config` - Webhooks, escalación, palabras clave
- `PATCH /api/tenants/{id}/email-config` - SMTP, plantillas, auto-respuesta  
- `PATCH /api/tenants/{id}/ai-config` - Modelos, proveedores, optimización
- `PATCH /api/tenants/{id}/fsm-config` - Estados, transiciones, timeouts
- `PATCH /api/tenants/{id}/payment-config` - Stripe, monedas, métodos de pago

### ✅ 2. Automatic API Documentation
**Estado:** COMPLETADO  
**Descripción:** FastAPI genera automáticamente Swagger UI en http://localhost:8003/docs con documentación interactiva y esquemas JSON actualizados en tiempo real.

**URL:** http://localhost:8003/docs

### ✅ 3. Database Schema & Demo Data
**Estado:** COMPLETADO  
**Descripción:** Base de datos PostgreSQL inicializada con todas las columnas de configuración y tenant demo funcionando (config_version: 5).

**Archivo:** `init_database.sql` - Script manual que reemplaza migraciones alembic

### ✅ 4. Python 3.14 Compatibility
**Estado:** COMPLETADO  
**Descripción:** Resueltos problemas de sintaxis Union (str | None → Union[str, None]) en shared/models/domain.py para compatibilidad con Python 3.14.

**Archivos modificados:** `shared/models/domain.py`

### ✅ 5. Simplified Tenant Manager Service
**Estado:** COMPLETADO  
**Descripción:** Creado tenant_manager_simple.py usando psycopg2 (síncrono) en lugar de asyncpg, funcionando perfectamente en puerto 8003.

**Archivo:** `tenant_manager_simple.py`  
**Puerto:** 8003  
**Tecnología:** psycopg2 + FastAPI

---

## 🔄 Pendientes (5/10)

### 🤔 6. AsyncPG vs Psycopg2 Decision
**Estado:** INVESTIGADO - Pendiente decisión  
**Descripción:** Proyecto diseñado para asyncpg pero funciona con psycopg2. Decisión pendiente: mantener simplicidad actual o migrar a asyncpg para producción con alta concurrencia.

**Análisis:**
- **AsyncPG:** ⚡ Muy rápido, 🚀 Miles de conexiones, 😵 Más complejo
- **Psycopg2:** 🐌 Más lento, 📝 Cientos de conexiones, 😊 Simple

**Recomendación:** Mantener psycopg2 para desarrollo, evaluar asyncpg para producción.

### 🛠 7. Fix Other Microservices AsyncPG Dependencies
**Estado:** PENDIENTE  
**Descripción:** Servicios orchestrator, recommender, checkout, rag-service, handoff, transcript requieren asyncpg==0.29.0. Evaluar si migrar todos a psycopg2 o arreglar compatibilidad asyncpg.

**Servicios afectados:**
- `services/orchestrator/`
- `services/recommender/` 
- `services/checkout/`
- `services/rag-service/`
- `services/handoff/`
- `services/transcript/`

**Opciones:**
1. Migrar todos a psycopg2 (simplicidad)
2. Arreglar asyncpg compatibility (rendimiento)
3. Híbrido: servicios críticos con asyncpg, otros con psycopg2

### ⚠️ 8. Model Adapter Service Issue
**Estado:** PENDIENTE - CRÍTICO  
**Descripción:** Servicio model-adapter (puerto 8005) no arranca correctamente. Revisar dependencias y configuración para LMStudio integration.

**Error:** Exit Code: 1 en task "model-adapter: start"  
**Puerto:** 8005  
**Comando:** `uvicorn app.main:app --app-dir services/model-adapter --port 8005`  
**Variables:** `MODEL_PROVIDER=lmstudio`

**Próximos pasos:**
1. Revisar logs de error específicos
2. Verificar dependencias en requirements.txt
3. Comprobar configuración de LMStudio
4. Validar estructura del servicio

### 🐳 9. Docker Compose Services Status
**Estado:** PENDIENTE  
**Descripción:** Docker-compose ps falló (Exit Code: 1). Verificar estado de contenedores PostgreSQL, Redis, Qdrant y otros servicios de infraestructura.

**Servicios esperados:**
- PostgreSQL (puerto 5432)
- Redis (puerto 6379) 
- Qdrant (puerto 6333)

**Próximos pasos:**
1. `docker-compose up -d` para levantar servicios
2. `docker-compose logs` para ver errores
3. Verificar conectividad de red
4. Revisar archivos de configuración

### 🚀 10. Production Readiness Assessment  
**Estado:** PENDIENTE  
**Descripción:** Evaluar qué se necesita para producción: migración completa a asyncpg, load testing, monitoring, logging estructurado, configuración de seguridad.

**Areas a evaluar:**
- **Performance:** AsyncPG vs Psycopg2 bajo carga
- **Security:** JWT, CORS, rate limiting, input validation
- **Monitoring:** Logs estructurados, métricas, health checks  
- **Scalability:** Horizontal scaling, load balancing
- **DevOps:** CI/CD, containerization, env management

---

## 📊 Prioridades

### 🔥 Críticas (Hacer ahora)
1. **Docker Status** (#9) - Infraestructura base
2. **Model Adapter** (#8) - Funcionalidad IA crítica

### ⭐ Importantes (Siguiente sprint)  
3. **Other Services** (#7) - Completar microservicios
4. **AsyncPG Decision** (#6) - Arquitectura definitiva

### 📈 Futuro (Planning)
5. **Production Ready** (#10) - Roadmap a producción

---

## 🔗 Enlaces Útiles

- **API Docs:** http://localhost:8003/docs
- **Tenant Demo:** `curl http://localhost:8003/api/tenants/demo-tenant`
- **Logs:** `docker-compose logs -f`
- **Database:** PostgreSQL en puerto 5432

---

## 📝 Notas de Desarrollo

### Decisiones Técnicas
- **Simplicidad sobre rendimiento** (por ahora)
- **FastAPI** para auto-documentación
- **Manual SQL** en lugar de migrations (compatibilidad)

### Lecciones Aprendidas  
- Python 3.14 requiere Union explícito
- AsyncPG añade complejidad innecesaria para APIs simples
- Pydantic validation es excelente para configuraciones

### Próximos Experimentos
- Load testing con ab/wrk
- Comparison asyncpg vs psycopg2 benchmarks  
- WebSocket implementation para chat real-time