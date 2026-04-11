"""
Integración con pytest para el framework de testing conversacional.
Permite ejecutar pruebas de conversación como tests pytest estándar.
"""
import pytest
import asyncio
import json
from typing import List, Dict, Any
from datetime import datetime

from ..config import config
from ..scenarios.enoturismo_scenarios import get_enoturismo_scenarios
from ..runners.automated_runner import ConversationTestRunner
from ..reports.report_generator import ReportGenerator
from ..auto_improvement.auto_optimizer import run_auto_optimization


class ConversationTestSuite:
    """Suite de pruebas conversacionales para pytest."""
    
    def __init__(self):
        self.test_runner = ConversationTestRunner()
        self.scenarios = get_enoturismo_scenarios()
        self.results = []
    
    async def run_all_scenarios(self):
        """Ejecuta todos los escenarios de prueba."""
        self.results = await self.test_runner.run_test_batch(self.scenarios)
        return self.results


# Instancia global para reutilizar en tests
conversation_suite = ConversationTestSuite()


class TestConversationFramework:
    """Clase de pruebas pytest para el framework conversacional."""
    
    @pytest.mark.asyncio
    async def test_wine_consultation_basic(self):
        """Prueba básica de consulta sobre vinos."""
        scenarios = [s for s in conversation_suite.scenarios if s.scenario_id == "wine_consultation_basic"]
        assert scenarios, "Escenario wine_consultation_basic no encontrado"
        
        results = await conversation_suite.test_runner.run_test_batch(scenarios)
        assert len(results) == 1
        
        result = results[0]
        assert result.passed, f"Prueba falló: {result.failure_reason}"
        assert result.evaluation_metrics.response_quality >= 0.7
    
    @pytest.mark.asyncio
    async def test_booking_flow_success(self):
        """Prueba flujo exitoso de reserva."""
        scenarios = [s for s in conversation_suite.scenarios if s.scenario_id == "booking_flow_success"]
        assert scenarios, "Escenario booking_flow_success no encontrado"
        
        results = await conversation_suite.test_runner.run_test_batch(scenarios)
        result = results[0]
        
        assert result.passed, f"Flujo de reserva falló: {result.failure_reason}"
        assert result.evaluation_metrics.conversation_completion >= 0.8
        assert "reserva confirmada" in result.final_response.lower()
    
    @pytest.mark.asyncio
    async def test_large_group_handoff(self):
        """Prueba handoff para grupos grandes."""
        scenarios = [s for s in conversation_suite.scenarios if s.scenario_id == "large_group_handoff"]
        assert scenarios, "Escenario large_group_handoff no encontrado"
        
        results = await conversation_suite.test_runner.run_test_batch(scenarios)
        result = results[0]
        
        # Para grupos grandes, esperamos handoff
        assert result.handoff_decision.should_handoff, "Debería hacer handoff para grupo grande"
        assert result.handoff_decision.channel == "sales"
        assert result.evaluation_metrics.handoff_quality >= 0.8
    
    @pytest.mark.asyncio
    async def test_complaint_escalation(self):
        """Prueba escalación de quejas."""
        scenarios = [s for s in conversation_suite.scenarios if s.scenario_id == "complaint_handling"]
        assert scenarios, "Escenario complaint_handling no encontrado"
        
        results = await conversation_suite.test_runner.run_test_batch(scenarios)
        result = results[0]
        
        assert result.handoff_decision.should_handoff, "Quejas deberían escalar a humano"
        assert result.handoff_decision.channel == "support"
        assert result.handoff_decision.priority == "high"
    
    @pytest.mark.asyncio
    async def test_multilingual_support(self):
        """Prueba soporte multiidioma."""
        scenarios = [s for s in conversation_suite.scenarios if s.scenario_id == "multilingual_english"]
        assert scenarios, "Escenario multilingual_english no encontrado"
        
        results = await conversation_suite.test_runner.run_test_batch(scenarios)
        result = results[0]
        
        assert result.passed, f"Soporte multiidioma falló: {result.failure_reason}"
        # Verificar que responde en inglés cuando se solicita
        assert any(word in result.final_response.lower() for word in ["wine", "tasting", "visit"])
    
    @pytest.mark.asyncio
    async def test_context_retention(self):
        """Prueba retención de contexto en conversación larga."""
        scenarios = [s for s in conversation_suite.scenarios if s.scenario_id == "context_retention"]
        
        if scenarios:
            results = await conversation_suite.test_runner.run_test_batch(scenarios)
            result = results[0]
            
            assert result.passed, f"Retención de contexto falló: {result.failure_reason}"
            assert result.evaluation_metrics.conversation_completion >= 0.7
        else:
            pytest.skip("Escenario context_retention no disponible")
    
    @pytest.mark.asyncio
    async def test_full_suite_performance(self):
        """Prueba rendimiento de toda la suite."""
        start_time = datetime.now()
        
        results = await conversation_suite.run_all_scenarios()
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Verificar que la suite completa se ejecuta en tiempo razonable
        assert execution_time < 300, f"Suite demoró demasiado: {execution_time}s"
        assert len(results) > 0, "No se ejecutaron pruebas"
        
        # Verificar tasa de éxito general
        passed_tests = sum(1 for r in results if r.passed)
        success_rate = passed_tests / len(results)
        
        assert success_rate >= 0.7, f"Tasa de éxito muy baja: {success_rate:.2%}"
        
        return results


# Fixtures para pytest
@pytest.fixture(scope="session")
def event_loop():
    """Crea un event loop para toda la sesión de pytest."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def conversation_test_results():
    """Fixture que ejecuta todas las pruebas y retorna resultados."""
    if not config.CONVERSATION_TESTING_ENABLED:
        pytest.skip("Testing conversacional deshabilitado")
    
    suite = ConversationTestSuite()
    results = await suite.run_all_scenarios()
    return results


@pytest.fixture(scope="session")
async def test_report(conversation_test_results):
    """Fixture que genera reporte de pruebas."""
    if conversation_test_results:
        report_generator = ReportGenerator()
        report_path = await report_generator.generate_html_report(
            conversation_test_results,
            "pytest_session_report.html"
        )
        return report_path
    return None


# Hooks de pytest para integración
def pytest_configure(config):
    """Configuración inicial de pytest."""
    config.addinivalue_line(
        "markers", "conversation: marca pruebas conversacionales"
    )
    config.addinivalue_line(
        "markers", "enoturismo: marca pruebas específicas de enoturismo"
    )


def pytest_collection_modifyitems(config, items):
    """Modifica items de la colección de pruebas."""
    for item in items:
        # Marcar pruebas conversacionales
        if "conversation" in item.nodeid:
            item.add_marker(pytest.mark.conversation)
        if "wine" in item.nodeid or "booking" in item.nodeid:
            item.add_marker(pytest.mark.enoturismo)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook para procesar resultados de pruebas."""
    outcome = yield
    rep = outcome.get_result()
    
    # Almacenar resultados para posterior análisis
    if rep.when == "call" and hasattr(item, 'conversation_result'):
        setattr(rep, 'conversation_result', item.conversation_result)


# Función para ejecutar optimización automática después de las pruebas
@pytest.fixture(scope="session", autouse=True)
async def auto_optimize_after_tests(conversation_test_results):
    """Ejecuta optimización automática al final de las pruebas."""
    yield  # Esperar a que terminen las pruebas
    
    if conversation_test_results and config.AUTO_IMPROVEMENT_ENABLED:
        try:
            optimization_result = await run_auto_optimization(conversation_test_results)
            print(f"\n🔧 Optimización automática completada:")
            print(f"   • Reglas generadas: {optimization_result.get('new_rules_generated', 0)}")
            print(f"   • Mejoras aplicadas: {optimization_result.get('improvements_applied', 0)}")
            
            if optimization_result.get('recommendations'):
                print(f"   • Recomendaciones manuales: {len(optimization_result['recommendations'])}")
        
        except Exception as e:
            print(f"\n⚠️  Error en optimización automática: {str(e)}")


# Comando CLI personalizado para ejecutar solo pruebas conversacionales
def run_conversation_tests():
    """Ejecuta solo las pruebas conversacionales."""
    pytest.main([
        __file__,
        "-v",
        "-m", "conversation",
        "--tb=short"
    ])


if __name__ == "__main__":
    # Permite ejecutar este archivo directamente
    run_conversation_tests()