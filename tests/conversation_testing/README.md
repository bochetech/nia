# Framework de Testing Conversacional - OpenChat

## Descripción General

Este framework permite probar automáticamente conversaciones de IA, evaluar su calidad y aplicar mejoras automáticas basándose en patrones de falla detectados. Está especialmente optimizado para escenarios de enoturismo y handoffs humanos.

## Características Principales

### 🤖 Testing Automatizado
- Simulación de conversaciones realistas
- Evaluación multi-dimensional de respuestas
- Detección automática de problemas de handoff
- Soporte para múltiples idiomas

### 📊 Análisis y Reportes
- Dashboard interactivo con visualizaciones
- Métricas detalladas de rendimiento
- Análisis de tendencias temporales
- Exportación de reportes HTML

### 🔧 Automejora Configurable
- Detección de patrones de falla
- Generación automática de reglas de mejora
- Aplicación opcional de optimizaciones
- Sistema de recomendaciones manuales

### ✅ Integración pytest
- Tests como casos pytest estándar
- Fixtures personalizadas
- Hooks para análisis post-ejecución
- Marcadores específicos para tipos de prueba

## Estructura del Framework

```
tests/conversation_testing/
├── config.py                 # Configuración principal
├── models.py                 # Modelos de datos
├── test_conversations.py     # Integración pytest
├── scenarios/
│   └── enoturismo_scenarios.py  # Escenarios específicos
├── evaluators/
│   └── conversation_evaluators.py  # Sistema de evaluación
├── runners/
│   └── automated_runner.py   # Orquestador de pruebas
├── reports/
│   └── report_generator.py   # Generación de reportes
└── auto_improvement/
    └── auto_optimizer.py     # Sistema de automejora
```

## Configuración

### Variables de Entorno Principales

```python
# Habilitar/deshabilitar testing
CONVERSATION_TESTING_ENABLED = True

# Automejora
AUTO_IMPROVEMENT_ENABLED = True
AUTO_APPLY_IMPROVEMENTS = False  # Recomendado: False para revisión manual

# Umbrales de evaluación
MIN_RESPONSE_QUALITY = 0.7
MIN_HANDOFF_QUALITY = 0.8
MIN_ROUTING_ACCURACY = 0.9
```

### Configuración de API

```python
# Endpoints para testing
CHAT_API_ENDPOINT = "http://localhost:8005/chat"
HANDOFF_API_ENDPOINT = "http://localhost:8005/handoff"

# Credenciales (configurar según ambiente)
API_KEY = "your-api-key"
TENANT_ID = "demo-tenant"
```

## Uso

### 1. Ejecutar Pruebas con pytest

```bash
# Ejecutar todas las pruebas conversacionales
pytest tests/conversation_testing/test_conversations.py -v

# Ejecutar solo pruebas de enoturismo
pytest tests/conversation_testing/test_conversations.py -m enoturismo

# Ejecutar con reporte detallado
pytest tests/conversation_testing/test_conversations.py --tb=long
```

### 2. Ejecutar Suite Completa

```python
from tests.conversation_testing.runners.automated_runner import ConversationTestRunner
from tests.conversation_testing.scenarios.enoturismo_scenarios import get_enoturismo_scenarios

# Crear runner
runner = ConversationTestRunner()

# Obtener escenarios
scenarios = get_enoturismo_scenarios()

# Ejecutar pruebas
results = await runner.run_test_batch(scenarios)

# Generar reporte
from tests.conversation_testing.reports.report_generator import ReportGenerator
report_gen = ReportGenerator()
await report_gen.generate_html_report(results, "mi_reporte.html")
```

### 3. Optimización Automática

```python
from tests.conversation_testing.auto_improvement.auto_optimizer import run_auto_optimization

# Ejecutar después de las pruebas
optimization_result = await run_auto_optimization(test_results)

print(f"Reglas generadas: {optimization_result['new_rules_generated']}")
print(f"Mejoras aplicadas: {optimization_result['improvements_applied']}")
```

## Escenarios de Prueba Incluidos

### Enoturismo Básico
- ✅ **wine_consultation_basic**: Consulta básica sobre vinos
- ✅ **wine_recommendation_advanced**: Recomendación avanzada con preferencias
- ✅ **booking_flow_success**: Flujo exitoso de reserva
- ✅ **booking_modification**: Modificación de reserva existente

### Handoffs y Escalación
- ✅ **large_group_handoff**: Transferencia para grupos grandes (>10 personas)
- ✅ **complaint_handling**: Manejo y escalación de quejas
- ✅ **complex_dietary_needs**: Necesidades dietéticas complejas

### Casos Especiales
- ✅ **multilingual_english**: Soporte para inglés
- ✅ **context_retention**: Retención de contexto en conversaciones largas
- ✅ **invalid_date_handling**: Manejo de fechas inválidas

## Métricas de Evaluación

### Calidad de Respuesta (0.0 - 1.0)
- Relevancia del contenido
- Precisión de la información
- Claridad de la comunicación
- Tono apropiado

### Calidad de Handoff (0.0 - 1.0)
- Decisión correcta de transferir
- Canal de handoff apropiado
- Contexto preservado
- Prioridad asignada correctamente

### Precisión de Enrutamiento (0.0 - 1.0)
- Canal correcto seleccionado
- Información de contacto precisa
- Horarios de disponibilidad

### Completitud de Conversación (0.0 - 1.0)
- Objetivos del usuario cumplidos
- Información necesaria recopilada
- Próximos pasos clarificados

## Personalización

### Agregar Nuevos Escenarios

```python
from tests.conversation_testing.models import ConversationScenario, UserMessage

# Crear nuevo escenario
nuevo_escenario = ConversationScenario(
    scenario_id="mi_escenario_personalizado",
    name="Mi Escenario",
    description="Descripción del escenario",
    messages=[
        UserMessage(
            role="user",
            content="Mensaje del usuario",
            timestamp=datetime.now()
        )
    ],
    expected_outcome="Resultado esperado",
    success_criteria={
        "response_quality": 0.8,
        "handoff_required": False
    },
    metadata={"category": "personalizado"}
)
```

### Configurar Evaluadores Personalizados

```python
class MiEvaluadorPersonalizado(ConversationEvaluator):
    def evaluate_response_quality(self, conversation, response):
        # Lógica personalizada de evaluación
        score = self._calcular_puntuacion_personalizada(response)
        return min(max(score, 0.0), 1.0)
```

## Troubleshooting

### Problemas Comunes

1. **Error de conexión a API**
   - Verificar que los servicios estén ejecutándose
   - Confirmar endpoints en configuración
   - Revisar credenciales de autenticación

2. **Pruebas fallan sistemáticamente**
   - Revisar umbrales de evaluación en config.py
   - Verificar que la base de conocimiento esté actualizada
   - Comprobar que los escenarios sean realistas

3. **Optimización automática no funciona**
   - Verificar AUTO_IMPROVEMENT_ENABLED = True
   - Confirmar suficientes datos de prueba (>10 resultados)
   - Revisar logs para errores específicos

### Logs y Debugging

```python
import logging

# Habilitar logs detallados
logging.basicConfig(level=logging.DEBUG)

# Ver logs específicos del framework
logger = logging.getLogger('conversation_testing')
logger.setLevel(logging.DEBUG)
```

## Integración CI/CD

### GitHub Actions

```yaml
name: Conversation Tests
on: [push, pull_request]

jobs:
  conversation-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.14
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run conversation tests
        run: pytest tests/conversation_testing/ -v
      - name: Upload test report
        uses: actions/upload-artifact@v2
        with:
          name: conversation-test-report
          path: conversation_test_report.html
```

## Roadmap

### Próximas Características
- [ ] Integración con LangSmith para tracking avanzado
- [ ] Soporte para múltiples modelos LLM simultáneos
- [ ] Testing de rendimiento y latencia
- [ ] Análisis de sentiment en tiempo real
- [ ] Dashboard en tiempo real con WebSocket
- [ ] Integración con sistemas de alertas (Slack, Teams)

### Mejoras Planificadas
- [ ] Caching inteligente de evaluaciones
- [ ] Paralelización de pruebas
- [ ] Métricas de costos de API
- [ ] Exportación a formatos adicionales (JSON, CSV)
- [ ] Configuración visual de escenarios

## Contribuir

1. Fork el repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## Licencia

MIT License - ver archivo LICENSE para detalles.

## Soporte

Para soporte técnico o consultas:
- Crear issue en GitHub
- Revisar documentación en `/docs/`
- Consultar logs en `/tests/conversation_testing/logs/`