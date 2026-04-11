"""
Framework de Testing Conversacional para OpenChat.

Este framework permite:
- Ejecutar pruebas automatizadas de conversaciones de IA
- Evaluar calidad de respuestas y decisiones de handoff
- Generar reportes detallados con visualizaciones
- Aplicar mejoras automáticas basadas en patrones de falla
- Integración completa con pytest

Ejemplos de uso:

    # Ejecutar todas las pruebas
    python run_conversation_tests.py test
    
    # Ejecutar prueba específica
    python run_conversation_tests.py test --scenario wine_consultation_basic
    
    # Generar reporte
    python run_conversation_tests.py test --report mi_reporte.html
    
    # Con optimización automática
    python run_conversation_tests.py test --optimize

    # Usar con pytest
    pytest test_conversations.py -v

Módulos principales:
- config: Configuración del framework
- models: Estructuras de datos para pruebas y resultados
- scenarios: Definición de escenarios de prueba
- evaluators: Sistema de evaluación de conversaciones
- runners: Orquestación de pruebas
- reports: Generación de reportes y dashboards
- auto_improvement: Sistema de automejora configurable

Para documentación completa, ver README.md
"""

__version__ = "1.0.0"
__author__ = "OpenChat Team"
__email__ = "team@openchat.ai"

from .config import config
from .models import (
    ConversationScenario,
    UserMessage,
    BotResponse,
    TestResult,
    EvaluationMetrics,
    HandoffDecision
)

# Importaciones principales para uso directo
from .scenarios.enoturismo_scenarios import get_enoturismo_scenarios
from .runners.automated_runner import ConversationTestRunner
from .reports.report_generator import ReportGenerator
from .evaluators.conversation_evaluators import ConversationEvaluator

# Funciones de conveniencia
async def run_quick_test(scenario_id: str = None):
    """
    Ejecuta una prueba rápida con un escenario específico o todos.
    
    Args:
        scenario_id: ID del escenario específico, o None para todos
        
    Returns:
        Lista de TestResult
    """
    from .runners.automated_runner import ConversationTestRunner
    from .scenarios.enoturismo_scenarios import get_enoturismo_scenarios
    
    runner = ConversationTestRunner()
    scenarios = get_enoturismo_scenarios()
    
    if scenario_id:
        scenarios = [s for s in scenarios if s.scenario_id == scenario_id]
        if not scenarios:
            raise ValueError(f"Escenario {scenario_id} no encontrado")
    
    return await runner.run_test_batch(scenarios)


async def generate_quick_report(results, filename: str = None):
    """
    Genera un reporte rápido de resultados.
    
    Args:
        results: Lista de TestResult
        filename: Nombre del archivo, se auto-genera si es None
        
    Returns:
        Path del archivo generado
    """
    from .reports.report_generator import ReportGenerator
    from datetime import datetime
    
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"quick_report_{timestamp}.html"
    
    generator = ReportGenerator()
    return await generator.generate_html_report(results, filename)


# Configuración de logging para el framework
import logging

def setup_logging(level=logging.INFO):
    """Configura logging para el framework."""
    logger = logging.getLogger('conversation_testing')
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
    
    return logger


# Auto-configurar logging
_logger = setup_logging()

# Exportar principales componentes
__all__ = [
    'config',
    'ConversationScenario',
    'UserMessage', 
    'BotResponse',
    'TestResult',
    'EvaluationMetrics',
    'HandoffDecision',
    'get_enoturismo_scenarios',
    'ConversationTestRunner',
    'ReportGenerator',
    'ConversationEvaluator',
    'run_quick_test',
    'generate_quick_report',
    'setup_logging'
]