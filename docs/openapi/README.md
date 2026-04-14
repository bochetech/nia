# NIA Platform — OpenAPI Specifications

Auto-generated from the live services running in Docker.

| Service | Port | Spec file | Endpoints |
|---------|------|-----------|-----------|
| Orchestrator | 8001 | [orchestrator.json](orchestrator.json) | 6 |
| RAG Service | 8002 | [rag-service.json](rag-service.json) | 6 |
| Tenant Manager | 8003 | [tenant-manager.json](tenant-manager.json) | 26+ |
| Recommender | 8004 | [recommender.json](recommender.json) | 2 |
| Model Adapter | 8005 | [model-adapter.json](model-adapter.json) | 4 |
| Checkout | 8006 | [checkout.json](checkout.json) | 4 |
| Handoff | 8007 | [handoff.json](handoff.json) | 4 |
| Transcript | 8008 | [transcript.json](transcript.json) | 6 |
| Fallback | 8009 | [fallback.json](fallback.json) | 2 |
| Telegram Gateway | 8010 | [telegram-gateway.json](telegram-gateway.json) | 3 |

## Regenerar

```bash
# Con los servicios corriendo en Docker:
for svc in orchestrator:8001 rag-service:8002 tenant-manager:8003 recommender:8004 \
  model-adapter:8005 checkout:8006 handoff:8007 transcript:8008 fallback:8009 \
  telegram-gateway:8010; do
  name="${svc%%:*}"; port="${svc##*:}"
  curl -s "http://localhost:$port/openapi.json" | python3 -m json.tool > "docs/openapi/${name}.json"
done
```

## Postman Collection

La colección Postman completa está en [`../NIA_Postman_Collection.json`](../NIA_Postman_Collection.json).

- **URLs**: Apuntan a `http://localhost:{port}` con valores por defecto para desarrollo local
- **Credenciales**: `admin@nia.local` / `changeme` (endpoint Login auto-guarda el token)
- **Tenant por defecto**: `demo_turismo`

> **Nota**: Los endpoints de skills (`/skills/*`) requieren rebuild del contenedor de tenant-manager para aparecer en el OpenAPI live. Ya están documentados en la colección Postman.

_Última actualización: 2026-04-13_
