#!/usr/bin/env python3
"""
Demo del Framework de Testing Conversacional.
Muestra cómo usar las características principales del framework.
"""
import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent.parent))

from tests.conversation_testing import (
    run_quick_test,
    generate_quick_report,
    get_enoturismo_scenarios,
    ConversationTestRunner,
    config
)


async def demo_basic_usage():
    """Demo básico del framework."""
    print("🎯 Demo: Uso Básico del Framework")
    print("=" * 50)
    
    # 1. Mostrar configuración
    print(f"📋 Configuración actual:")
    print(f"   • Testing habilitado: {config.CONVERSATION_TESTING_ENABLED}")
    print(f"   • Endpoint: {config.CHAT_API_ENDPOINT}")
    print(f"   • Tenant: {config.TENANT_ID}")
    print()
    
    if not config.CONVERSATION_TESTING_ENABLED:
        print("⚠️  Testing deshabilitado. Habilitando para demo...")
        config.CONVERSATION_TESTING_ENABLED = True
    
    # 2. Listar escenarios disponibles
    scenarios = get_enoturismo_scenarios()
    print(f"📝 Escenarios disponibles: {len(scenarios)}")
    for scenario in scenarios[:3]:  # Mostrar primeros 3
        print(f"   • {scenario.scenario_id}: {scenario.name}")
    print("   ... y más\n")
    
    # 3. Ejecutar prueba rápida con un escenario específico
    print("🚀 Ejecutando prueba de consulta básica sobre vinos...")
    try:
        results = await run_quick_test("wine_consultation_basic")
        
        if results:
            result = results[0]
            print(f"✅ Prueba completada:")
            print(f"   • Resultado: {'✅ Exitoso' if result.passed else '❌ Falló'}")
            print(f"   • Calidad respuesta: {result.evaluation_metrics.response_quality:.2f}")
            print(f"   • Tiempo ejecución: {result.execution_time:.2f}s")
            if not result.passed:
                print(f"   • Razón fallo: {result.failure_reason}")
        else:
            print("⚠️  No se obtuvieron resultados")
        
    except Exception as e:
        print(f"❌ Error ejecutando prueba: {str(e)}")
        print("   (Esto es normal en demo sin API real)")
    
    print()


async def demo_batch_testing():
    """Demo de ejecución de múltiples pruebas."""
    print("🎯 Demo: Ejecución en Lote")
    print("=" * 50)
    
    runner = ConversationTestRunner()
    scenarios = get_enoturismo_scenarios()
    
    # Ejecutar primeros 3 escenarios para demo
    test_scenarios = scenarios[:3]
    
    print(f"🧪 Ejecutando {len(test_scenarios)} pruebas...")
    
    try:
        results = await runner.run_test_batch(test_scenarios)
        
        # Estadísticas
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        
        print(f"📊 Resultados:")
        print(f"   • Total ejecutadas: {len(results)}")
        print(f"   • Exitosas: {passed}")
        print(f"   • Fallidas: {failed}")
        print(f"   • Tasa éxito: {(passed/len(results)*100):.1f}%")
        
        # Mostrar detalles de cada prueba
        print(f"\n📋 Detalle por prueba:")
        for result in results:
            status = "✅" if result.passed else "❌"
            print(f"   {status} {result.scenario_id}")
            print(f"      Calidad: {result.evaluation_metrics.response_quality:.2f}")
            if result.handoff_decision and result.handoff_decision.should_handoff:
                print(f"      Handoff: {result.handoff_decision.channel}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error en ejecución: {str(e)}")
        return []


async def demo_report_generation(results=None):
    """Demo de generación de reportes."""
    print("🎯 Demo: Generación de Reportes")
    print("=" * 50)
    
    if not results:
        print("⚠️  No hay resultados previos. Creando datos de ejemplo...")
        # Crear resultados de ejemplo para el demo
        from tests.conversation_testing.models import TestResult, EvaluationMetrics, HandoffDecision
        from datetime import datetime
        
        results = [
            TestResult(
                scenario_id="demo_scenario_1",
                passed=True,
                evaluation_metrics=EvaluationMetrics(
                    response_quality=0.85,
                    handoff_quality=0.90,
                    channel_routing_accuracy=0.88,
                    conversation_completion=0.92
                ),
                execution_time=2.3,
                timestamp=datetime.now(),
                final_response="Ejemplo de respuesta exitosa",
                handoff_decision=HandoffDecision(
                    should_handoff=False,
                    confidence=0.75,
                    channel="none",
                    priority="low",
                    context_summary="Consulta básica resuelta"
                )
            ),
            TestResult(
                scenario_id="demo_scenario_2", 
                passed=False,
                evaluation_metrics=EvaluationMetrics(
                    response_quality=0.45,
                    handoff_quality=0.60,
                    channel_routing_accuracy=0.70,
                    conversation_completion=0.30
                ),
                execution_time=1.8,
                timestamp=datetime.now(),
                final_response="Respuesta de baja calidad",
                failure_reason="Calidad de respuesta por debajo del umbral",
                handoff_decision=HandoffDecision(
                    should_handoff=True,
                    confidence=0.85,
                    channel="support",
                    priority="medium",
                    context_summary="Problema no resuelto"
                )
            )
        ]
    
    try:
        report_path = await generate_quick_report(results, "demo_report.html")
        print(f"📄 Reporte generado: {report_path}")
        print(f"   • Incluye {len(results)} resultados")
        print(f"   • Dashboard interactivo con gráficos")
        print(f"   • Análisis de métricas y tendencias")
        
    except Exception as e:
        print(f"❌ Error generando reporte: {str(e)}")


async def demo_optimization():
    """Demo del sistema de optimización automática."""
    print("🎯 Demo: Sistema de Optimización Automática")
    print("=" * 50)
    
    # Verificar configuración
    print(f"🔧 Estado automejora:")
    print(f"   • Habilitada: {config.AUTO_IMPROVEMENT_ENABLED}")
    print(f"   • Auto-aplicar: {config.AUTO_APPLY_IMPROVEMENTS}")
    print()
    
    if not config.AUTO_IMPROVEMENT_ENABLED:
        print("⚠️  Automejora deshabilitada. Habilitando para demo...")
        config.AUTO_IMPROVEMENT_ENABLED = True
    
    # Crear resultados de ejemplo con fallas para análisis
    from tests.conversation_testing.models import TestResult, EvaluationMetrics
    from tests.conversation_testing.auto_improvement import run_auto_optimization
    from datetime import datetime
    
    # Simular resultados con patrones de falla
    sample_results = []
    
    # Fallas por baja calidad de respuesta
    for i in range(5):
        result = TestResult(
            scenario_id=f"wine_consultation_{i}",
            passed=False,
            evaluation_metrics=EvaluationMetrics(
                response_quality=0.4,  # Baja calidad
                handoff_quality=0.8,
                channel_routing_accuracy=0.9,
                conversation_completion=0.5
            ),
            execution_time=2.0,
            timestamp=datetime.now(),
            final_response="Respuesta vaga e inexacta",
            failure_reason="Calidad de respuesta insuficiente"
        )
        sample_results.append(result)
    
    # Fallas por handoff incorrecto
    for i in range(3):
        result = TestResult(
            scenario_id=f"booking_flow_{i}",
            passed=False,
            evaluation_metrics=EvaluationMetrics(
                response_quality=0.7,
                handoff_quality=0.3,  # Handoff pobre
                channel_routing_accuracy=0.6,
                conversation_completion=0.4
            ),
            execution_time=1.5,
            timestamp=datetime.now(),
            final_response="Transferencia inapropiada",
            failure_reason="Decisión de handoff incorrecta"
        )
        sample_results.append(result)
    
    print(f"📊 Analizando {len(sample_results)} resultados con fallas...")
    
    try:
        optimization_result = await run_auto_optimization(sample_results)
        
        print(f"✅ Análisis completado:")
        print(f"   • Reglas de mejora generadas: {optimization_result.get('new_rules_generated', 0)}")
        print(f"   • Mejoras aplicadas: {optimization_result.get('improvements_applied', 0)}")
        
        # Mostrar insights generados
        pattern_analysis = optimization_result.get('pattern_analysis', {})
        insights = pattern_analysis.get('insights', [])
        
        if insights:
            print(f"\n💡 Insights detectados:")
            for insight in insights[:3]:
                print(f"   • {insight}")
        
        # Mostrar recomendaciones
        recommendations = optimization_result.get('recommendations', [])
        if recommendations:
            print(f"\n📝 Recomendaciones:")
            for rec in recommendations[:3]:
                print(f"   • {rec['description']} (Prioridad: {rec['priority']})")
        
    except Exception as e:
        print(f"❌ Error en optimización: {str(e)}")


async def main():
    """Función principal del demo."""
    print("🎪 Bienvenido al Demo del Framework de Testing Conversacional")
    print("=" * 65)
    print()
    
    # Ejecutar demos en secuencia
    demos = [
        ("Uso Básico", demo_basic_usage),
        ("Ejecución en Lote", demo_batch_testing), 
        ("Generación de Reportes", demo_report_generation),
        ("Optimización Automática", demo_optimization)
    ]
    
    results = []
    
    for name, demo_func in demos:
        print(f"\n{'='*65}")
        try:
            if demo_func == demo_batch_testing:
                batch_results = await demo_func()
                results.extend(batch_results)
            elif demo_func == demo_report_generation and results:
                await demo_func(results)
            else:
                await demo_func()
        except Exception as e:
            print(f"❌ Error en demo '{name}': {str(e)}")
        
        print(f"{'='*65}")
        
        # Pausa entre demos
        print("\nPresiona Enter para continuar al siguiente demo...")
        try:
            input()
        except KeyboardInterrupt:
            print("\n👋 Demo interrumpido por el usuario")
            return
    
    print(f"\n🎉 Demo completado!")
    print(f"📚 Para más información, consulta:")
    print(f"   • README.md para documentación completa")
    print(f"   • run_conversation_tests.py --help para opciones CLI")
    print(f"   • test_conversations.py para integración pytest")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Demo cancelado")
    except Exception as e:
        print(f"\n❌ Error ejecutando demo: {str(e)}")
        sys.exit(1)