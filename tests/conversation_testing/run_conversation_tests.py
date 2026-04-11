#!/usr/bin/env python3
"""
Script de inicio para el Framework de Testing Conversacional.
Proporciona comandos CLI para ejecutar pruebas, generar reportes y aplicar optimizaciones.
"""
import asyncio
import argparse
import sys
import os
from datetime import datetime
from pathlib import Path

# Agregar el directorio raíz al path para importaciones
sys.path.append(str(Path(__file__).parent.parent.parent))

from tests.conversation_testing.config import config
from tests.conversation_testing.scenarios.enoturismo_scenarios import get_enoturismo_scenarios
from tests.conversation_testing.runners.automated_runner import ConversationTestRunner
from tests.conversation_testing.reports.report_generator import ReportGenerator
from tests.conversation_testing.auto_improvement.auto_optimizer import run_auto_optimization
from tests.conversation_testing.models import TestResult


def print_banner():
    """Imprime banner del framework."""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║              Framework de Testing Conversacional             ║
    ║                         OpenChat                             ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_config_status():
    """Imprime estado actual de la configuración."""
    print("📋 Estado de Configuración:")
    print(f"   • Testing habilitado: {'✅' if config.CONVERSATION_TESTING_ENABLED else '❌'}")
    print(f"   • Automejora habilitada: {'✅' if config.AUTO_IMPROVEMENT_ENABLED else '❌'}")
    print(f"   • Aplicar mejoras automáticamente: {'✅' if config.AUTO_APPLY_IMPROVEMENTS else '❌'}")
    print(f"   • Endpoint chat: {config.CHAT_API_ENDPOINT}")
    print(f"   • Tenant ID: {config.TENANT_ID}")
    print()


async def run_tests_command(args):
    """Ejecuta las pruebas conversacionales."""
    print("🚀 Iniciando pruebas conversacionales...")
    
    if not config.CONVERSATION_TESTING_ENABLED:
        print("❌ Error: Testing conversacional deshabilitado en configuración")
        return False
    
    # Crear runner
    runner = ConversationTestRunner()
    
    # Obtener escenarios
    if args.scenario:
        # Ejecutar escenario específico
        all_scenarios = get_enoturismo_scenarios()
        scenarios = [s for s in all_scenarios if s.scenario_id == args.scenario]
        if not scenarios:
            print(f"❌ Error: Escenario '{args.scenario}' no encontrado")
            available = [s.scenario_id for s in all_scenarios]
            print(f"Escenarios disponibles: {', '.join(available)}")
            return False
    else:
        # Ejecutar todos los escenarios
        scenarios = get_enoturismo_scenarios()
    
    print(f"📝 Ejecutando {len(scenarios)} escenarios de prueba...")
    
    # Ejecutar pruebas
    try:
        results = await runner.run_test_batch(scenarios)
        
        # Estadísticas
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        success_rate = (passed / len(results)) * 100 if results else 0
        
        print(f"\n📊 Resultados:")
        print(f"   • Pruebas ejecutadas: {len(results)}")
        print(f"   • Exitosas: {passed} ✅")
        print(f"   • Fallidas: {failed} ❌")
        print(f"   • Tasa de éxito: {success_rate:.1f}%")
        
        # Mostrar fallas si las hay
        if failed > 0:
            print(f"\n❌ Pruebas fallidas:")
            for result in results:
                if not result.passed:
                    print(f"   • {result.scenario_id}: {result.failure_reason}")
        
        # Generar reporte si se solicita
        if args.report:
            await generate_report(results, args.report)
        
        # Ejecutar optimización si está habilitada
        if args.optimize and config.AUTO_IMPROVEMENT_ENABLED:
            await run_optimization(results)
        
        return len(results) > 0 and success_rate >= 70
        
    except Exception as e:
        print(f"❌ Error ejecutando pruebas: {str(e)}")
        return False


async def generate_report(results, filename=None):
    """Genera reporte HTML de los resultados."""
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"conversation_test_report_{timestamp}.html"
    
    print(f"📄 Generando reporte: {filename}")
    
    try:
        report_generator = ReportGenerator()
        report_path = await report_generator.generate_html_report(results, filename)
        print(f"✅ Reporte generado: {report_path}")
        return report_path
    except Exception as e:
        print(f"❌ Error generando reporte: {str(e)}")
        return None


async def run_optimization(results):
    """Ejecuta optimización automática."""
    print("🔧 Iniciando optimización automática...")
    
    try:
        optimization_result = await run_auto_optimization(results)
        
        print(f"✅ Optimización completada:")
        print(f"   • Reglas generadas: {optimization_result.get('new_rules_generated', 0)}")
        print(f"   • Mejoras aplicadas: {optimization_result.get('improvements_applied', 0)}")
        
        recommendations = optimization_result.get('recommendations', [])
        if recommendations:
            print(f"   • Recomendaciones manuales: {len(recommendations)}")
            for rec in recommendations[:3]:  # Mostrar primeras 3
                print(f"     - {rec['description']}")
        
        return optimization_result
        
    except Exception as e:
        print(f"❌ Error en optimización: {str(e)}")
        return None


def list_scenarios_command():
    """Lista todos los escenarios disponibles."""
    scenarios = get_enoturismo_scenarios()
    
    print(f"📝 Escenarios disponibles ({len(scenarios)}):")
    print()
    
    categories = {}
    for scenario in scenarios:
        category = scenario.metadata.get('category', 'general')
        if category not in categories:
            categories[category] = []
        categories[category].append(scenario)
    
    for category, scenarios_in_cat in categories.items():
        print(f"📂 {category.title()}:")
        for scenario in scenarios_in_cat:
            print(f"   • {scenario.scenario_id}: {scenario.name}")
            print(f"     {scenario.description}")
        print()


async def check_health_command():
    """Verifica la salud del sistema."""
    print("🔍 Verificando estado del sistema...")
    
    health_status = {
        "config": True,
        "api_connection": False,
        "scenarios": False,
        "evaluators": False
    }
    
    # Verificar configuración
    try:
        if config.CONVERSATION_TESTING_ENABLED:
            health_status["config"] = True
            print("✅ Configuración: OK")
        else:
            print("⚠️  Configuración: Testing deshabilitado")
    except Exception as e:
        health_status["config"] = False
        print(f"❌ Configuración: Error - {str(e)}")
    
    # Verificar conexión API
    try:
        runner = ConversationTestRunner()
        # Aquí podríamos hacer un ping al API
        health_status["api_connection"] = True
        print("✅ API: Configuración válida")
    except Exception as e:
        health_status["api_connection"] = False
        print(f"❌ API: Error de configuración - {str(e)}")
    
    # Verificar escenarios
    try:
        scenarios = get_enoturismo_scenarios()
        if scenarios:
            health_status["scenarios"] = True
            print(f"✅ Escenarios: {len(scenarios)} cargados")
        else:
            print("⚠️  Escenarios: No hay escenarios disponibles")
    except Exception as e:
        health_status["scenarios"] = False
        print(f"❌ Escenarios: Error cargando - {str(e)}")
    
    # Verificar evaluadores
    try:
        from tests.conversation_testing.evaluators.conversation_evaluators import ConversationEvaluator
        evaluator = ConversationEvaluator()
        health_status["evaluators"] = True
        print("✅ Evaluadores: OK")
    except Exception as e:
        health_status["evaluators"] = False
        print(f"❌ Evaluadores: Error - {str(e)}")
    
    overall_health = all(health_status.values())
    print(f"\n🏥 Estado general: {'✅ Saludable' if overall_health else '❌ Requiere atención'}")
    
    return overall_health


def main():
    """Función principal del CLI."""
    parser = argparse.ArgumentParser(
        description="Framework de Testing Conversacional - OpenChat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python run_conversation_tests.py test                    # Ejecutar todas las pruebas
  python run_conversation_tests.py test --scenario wine_consultation_basic
  python run_conversation_tests.py test --report mi_reporte.html --optimize
  python run_conversation_tests.py scenarios              # Listar escenarios
  python run_conversation_tests.py health                 # Verificar sistema
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comando test
    test_parser = subparsers.add_parser('test', help='Ejecutar pruebas conversacionales')
    test_parser.add_argument('--scenario', '-s', type=str, 
                           help='Ejecutar escenario específico')
    test_parser.add_argument('--report', '-r', type=str,
                           help='Generar reporte HTML (opcional: nombre archivo)')
    test_parser.add_argument('--optimize', '-o', action='store_true',
                           help='Ejecutar optimización automática después de las pruebas')
    test_parser.add_argument('--no-banner', action='store_true',
                           help='No mostrar banner inicial')
    
    # Comando scenarios
    scenarios_parser = subparsers.add_parser('scenarios', help='Listar escenarios disponibles')
    
    # Comando health
    health_parser = subparsers.add_parser('health', help='Verificar estado del sistema')
    
    # Comando report (solo generar reporte)
    report_parser = subparsers.add_parser('report', help='Generar reporte desde resultados previos')
    report_parser.add_argument('results_file', type=str, help='Archivo JSON con resultados')
    report_parser.add_argument('--output', '-o', type=str, help='Nombre del archivo HTML')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Mostrar banner si no está deshabilitado
    if not getattr(args, 'no_banner', False):
        print_banner()
        print_config_status()
    
    # Ejecutar comando
    if args.command == 'test':
        success = asyncio.run(run_tests_command(args))
        sys.exit(0 if success else 1)
    
    elif args.command == 'scenarios':
        list_scenarios_command()
    
    elif args.command == 'health':
        healthy = asyncio.run(check_health_command())
        sys.exit(0 if healthy else 1)
    
    elif args.command == 'report':
        # Implementar generación de reporte desde archivo
        print(f"⚠️  Comando 'report' desde archivo no implementado aún")
        sys.exit(1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()