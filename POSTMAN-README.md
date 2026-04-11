# 📮 Colección de Postman para NIA - Neural Intelligence Assistant

Esta colección completa te permite probar todos los servicios del sistema NIA con ejemplos reales y configuraciones listas para usar.

## 🚀 Archivos incluidos

1. **`NIA-Postman-Collection.json`** - Colección principal con todos los endpoints
2. **`NIA-Environment-Development.json`** - Variables de entorno para desarrollo local
3. **`NIA-Environment-Production.json`** - Variables de entorno para producción

## 📋 Servicios incluidos

### 🎯 **Orchestrator Service (Puerto 8001)**
- ✅ Send Chat Message
- ✅ Stream Chat (SSE)
- ✅ Get Session State
- ✅ Health Check

### 📚 **RAG Service (Puerto 8002)**
- ✅ Query Knowledge Base
- ✅ Ingest Document (PDF/texto)
- ✅ Ingest JSON Knowledge
- ✅ Delete Document
- ✅ Health Check

### 👥 **Tenant Manager (Puerto 8003)**
- ✅ Create Tenant
- ✅ List Tenants (con paginación)
- ✅ Get Tenant
- ✅ Update Tenant
- ✅ Create API Key
- ✅ Generate Widget Token
- ✅ Suspend Tenant
- ✅ Health Check

### 🎯 **Recommender Service (Puerto 8004)**
- ✅ Get Recommendations
- ✅ Health Check

### 🤖 **Model Adapter (Puerto 8005)**
- ✅ Chat Completions
- ✅ Chat Stream (SSE)
- ✅ Generate Embeddings
- ✅ Health Check

### 💳 **Checkout Service (Puerto 8006)**
- ✅ Create Booking Intent
- ✅ Create Checkout Session
- ✅ Health Check

### 🤝 **Handoff Service (Puerto 8007)**
- ✅ Create Handoff Case
- ✅ Get Handoff Status
- ✅ Health Check

### 📝 **Transcript Service (Puerto 8008)**
- ✅ Save Message
- ✅ Get Conversation History
- ✅ Export to Email
- ✅ Create Lead
- ✅ Health Check

### 🔄 **Fallback Service (Puerto 8009)**
- ✅ Get Fallback Message
- ✅ Health Check

### 🎨 **Demo Server (Puerto 8080)**
- ✅ Get Demo Page
- ✅ Get Widget Config
- ✅ Chat Proxy
- ✅ Create Session (Demo)

## 🔧 Configuración rápida

### 1. Importar en Postman

1. Abre Postman
2. Haz clic en **Import**
3. Selecciona **`NIA-Postman-Collection.json`**
4. Importa también los archivos de entorno:
   - `NIA-Environment-Development.json`
   - `NIA-Environment-Production.json`

### 2. Configurar entorno

1. Selecciona el entorno **"NIA Development"** para desarrollo local
2. O **"NIA Production"** para producción
3. Actualiza las variables según tu configuración:

```json
{
  "base_url": "http://localhost",        // URL base de tus servicios
  "tenant_id": "demo-tenant",            // ID del tenant de prueba
  "auth_token": "Bearer your-token",     // Token JWT válido
  "admin_token": "Bearer admin-token"    // Token de administrador
}
```

### 3. Ejecutar requests

Todos los requests incluyen:
- ✅ **Ejemplos reales** con datos de turismo de Asturias
- ✅ **Tests automáticos** para verificar respuestas
- ✅ **Scripts pre-request** para generar UUIDs y preparar datos
- ✅ **Variables dinámicas** que se actualizan automáticamente

## 🎯 Ejemplos de uso

### Ejemplo 1: Conversación completa
```
1. POST /v1/chat (Orchestrator) - "Busco senderismo en Asturias"
2. POST /v1/rag/query (RAG) - Busca información relevante
3. POST /v1/recommendations (Recommender) - Obtiene recomendaciones
4. POST /v1/checkout/booking-intents (Checkout) - Crear intención de reserva
```

### Ejemplo 2: Gestión de tenants
```
1. POST /api/tenants (Tenant Manager) - Crear tenant
2. POST /api/tenants/{id}/api-keys - Generar API key
3. POST /api/tenants/{id}/widget-token - Token para widget
```

### Ejemplo 3: Ingesta de conocimiento
```
1. POST /v1/rag/ingest-json (RAG) - Subir actividades turísticas
2. POST /v1/rag/query (RAG) - Verificar que se pueden consultar
```

## 🧪 Tests automáticos incluidos

Cada request incluye tests que verifican:
- ✅ Status codes exitosos (200, 201, 202, 204)
- ✅ Tiempo de respuesta < 5 segundos
- ✅ Estructura JSON válida
- ✅ Campos requeridos en la respuesta
- ✅ Tipos de datos correctos

## 🔐 Autenticación

La colección soporta múltiples métodos de autenticación:

### JWT Tokens
```http
Authorization: Bearer eyJ0eXAiOiJKV1Q...
```

### API Keys
```http
X-API-Key: nia_api_key_12345
```

### Tenant Headers
```http
X-Tenant-ID: demo-tenant
```

## 🌐 Variables de entorno

### Variables globales
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `base_url` | URL base de la API | `http://localhost` |
| `tenant_id` | ID del tenant actual | `demo-tenant` |
| `session_id` | ID de sesión (auto-generado) | UUID |
| `auth_token` | Token de autenticación | `Bearer ...` |

### Variables por servicio
| Variable | Puerto | Servicio |
|----------|--------|----------|
| `orchestrator_port` | 8001 | Orchestrator |
| `rag_port` | 8002 | RAG Service |
| `tenant_manager_port` | 8003 | Tenant Manager |
| `recommender_port` | 8004 | Recommender |
| `model_adapter_port` | 8005 | Model Adapter |
| `checkout_port` | 8006 | Checkout |
| `handoff_port` | 8007 | Handoff |
| `transcript_port` | 8008 | Transcript |
| `fallback_port` | 8009 | Fallback |
| `demo_port` | 8080 | Demo Server |

## 🚀 Empezar ahora

### Desarrollo local
1. Levanta los servicios con Docker Compose:
   ```bash
   docker-compose up -d
   ```

2. Usa el entorno **"NIA Development"**

3. Ejecuta el request **"Health Check"** de cada servicio para verificar conectividad

### Producción
1. Configura el entorno **"NIA Production"**
2. Actualiza las URLs y tokens
3. Ejecuta los tests para verificar que todo funciona

## 🎯 Tips y trucos

### 1. Session IDs automáticos
Los `session_id` se generan automáticamente en cada request usando `{{$randomUUID}}`

### 2. Requests encadenados
Los tests guardan automáticamente IDs importantes para usar en requests posteriores:
- `tenant_id` al crear tenants
- `session_id` de respuestas de chat
- `auth_token` de login exitoso

### 3. Debugging
Revisa la consola de Postman para logs detallados de cada request.

### 4. Bulk testing
Usa el **Collection Runner** para ejecutar todos los tests automáticamente.

## 📞 Soporte

Si encuentras problemas:
1. Verifica que todos los servicios estén ejecutándose
2. Revisa los logs en la consola de Postman
3. Asegúrate de estar usando el entorno correcto
4. Verifica que los tokens no hayan expirado

---

**¡Listo para probar NIA! 🚀**

Esta colección te permitirá probar todo el sistema completo con ejemplos reales de turismo en Asturias.