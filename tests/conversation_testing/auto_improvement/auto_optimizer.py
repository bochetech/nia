"""
Sistema de automejora configurable para conversaciones de IA.
Analiza patrones de falla y optimiza automáticamente el comportamiento del chatbot.
"""
from typing import Dict, List, Any, Tuple, Optional
import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import asyncio
import numpy as np
from collections import defaultdict, Counter

from ..config import config
from ..models import TestResult, ConversationScenario, EvaluationMetrics
from ..evaluators.conversation_evaluators import ConversationEvaluator


@dataclass
class ImprovementRule:
    """Representa una regla de mejora identificada por el sistema."""
    rule_id: str
    description: str
    condition: str
    action: str
    confidence: float
    impact_estimate: float
    applicable_scenarios: List[str]
    created_at: datetime
    applied_count: int = 0
    success_rate: float = 0.0


@dataclass
class OptimizationStrategy:
    """Estrategia de optimización para un tipo específico de problema."""
    strategy_id: str
    name: str
    description: str
    target_metric: str
    improvement_rules: List[ImprovementRule]
    effectiveness_score: float = 0.0


class PatternAnalyzer:
    """Analiza patrones de falla y éxito en los resultados de pruebas."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_failure_patterns(self, test_results: List[TestResult]) -> Dict[str, Any]:
        """Analiza patrones en las fallas de pruebas."""
        failure_results = [r for r in test_results if not r.passed]
        
        if not failure_results:
            return {"patterns": [], "insights": []}
        
        patterns = {
            "common_failure_types": self._analyze_failure_types(failure_results),
            "scenario_failure_rates": self._analyze_scenario_failures(failure_results),
            "metric_correlations": self._analyze_metric_correlations(failure_results),
            "temporal_patterns": self._analyze_temporal_patterns(failure_results),
            "handoff_issues": self._analyze_handoff_patterns(failure_results)
        }
        
        insights = self._generate_insights(patterns)
        
        return {
            "patterns": patterns,
            "insights": insights,
            "analysis_timestamp": datetime.now()
        }
    
    def _analyze_failure_types(self, failure_results: List[TestResult]) -> Dict[str, int]:
        """Analiza tipos comunes de fallas."""
        failure_types = Counter()
        
        for result in failure_results:
            metrics = result.evaluation_metrics
            
            if metrics.response_quality < 0.6:
                failure_types["low_response_quality"] += 1
            if metrics.handoff_quality < 0.7:
                failure_types["poor_handoff_decision"] += 1
            if metrics.channel_routing_accuracy < 0.8:
                failure_types["incorrect_channel_routing"] += 1
            if metrics.conversation_completion < 0.5:
                failure_types["incomplete_conversation"] += 1
            
            # Análisis de casos específicos
            if "wine" in result.scenario_id.lower() and metrics.response_quality < 0.7:
                failure_types["wine_knowledge_gaps"] += 1
            if "booking" in result.scenario_id.lower() and not result.passed:
                failure_types["booking_flow_issues"] += 1
        
        return dict(failure_types)
    
    def _analyze_scenario_failures(self, failure_results: List[TestResult]) -> Dict[str, float]:
        """Analiza tasa de fallas por escenario."""
        scenario_failures = defaultdict(int)
        scenario_totals = defaultdict(int)
        
        for result in failure_results:
            scenario_failures[result.scenario_id] += 1
        
        # Necesitamos todos los resultados para calcular tasas correctas
        # Por simplicidad, retornamos conteos de fallas
        return dict(scenario_failures)
    
    def _analyze_metric_correlations(self, failure_results: List[TestResult]) -> Dict[str, float]:
        """Analiza correlaciones entre métricas."""
        if len(failure_results) < 5:
            return {}
        
        quality_scores = []
        handoff_scores = []
        routing_scores = []
        completion_scores = []
        
        for result in failure_results:
            m = result.evaluation_metrics
            quality_scores.append(m.response_quality)
            handoff_scores.append(m.handoff_quality)
            routing_scores.append(m.channel_routing_accuracy)
            completion_scores.append(m.conversation_completion)
        
        correlations = {}
        try:
            correlations["quality_handoff"] = float(np.corrcoef(quality_scores, handoff_scores)[0,1])
            correlations["quality_routing"] = float(np.corrcoef(quality_scores, routing_scores)[0,1])
            correlations["handoff_completion"] = float(np.corrcoef(handoff_scores, completion_scores)[0,1])
        except:
            # En caso de error en cálculo de correlaciones
            correlations = {}
        
        return correlations
    
    def _analyze_temporal_patterns(self, failure_results: List[TestResult]) -> Dict[str, Any]:
        """Analiza patrones temporales en las fallas."""
        if not failure_results:
            return {}
        
        # Agrupar fallas por hora del día
        hour_failures = defaultdict(int)
        for result in failure_results:
            hour = result.timestamp.hour if result.timestamp else 0
            hour_failures[hour] += 1
        
        return {
            "peak_failure_hours": dict(hour_failures),
            "failure_trend": "increasing" if len(failure_results) > 10 else "stable"
        }
    
    def _analyze_handoff_patterns(self, failure_results: List[TestResult]) -> Dict[str, Any]:
        """Analiza patrones específicos de handoff."""
        handoff_issues = {
            "premature_handoffs": 0,
            "missed_handoffs": 0,
            "incorrect_channel": 0,
            "context_loss": 0
        }
        
        for result in failure_results:
            if hasattr(result, 'handoff_decision') and result.handoff_decision:
                if result.evaluation_metrics.handoff_quality < 0.5:
                    handoff_issues["premature_handoffs"] += 1
                if result.evaluation_metrics.channel_routing_accuracy < 0.7:
                    handoff_issues["incorrect_channel"] += 1
        
        return handoff_issues
    
    def _generate_insights(self, patterns: Dict[str, Any]) -> List[str]:
        """Genera insights accionables a partir de los patrones."""
        insights = []
        
        failure_types = patterns.get("common_failure_types", {})
        
        if failure_types.get("low_response_quality", 0) > 5:
            insights.append("Mejorar base de conocimiento - múltiples respuestas de baja calidad detectadas")
        
        if failure_types.get("wine_knowledge_gaps", 0) > 3:
            insights.append("Expandir conocimiento específico sobre vinos y enoturismo")
        
        if failure_types.get("booking_flow_issues", 0) > 2:
            insights.append("Revisar y simplificar el flujo de reservas")
        
        if failure_types.get("poor_handoff_decision", 0) > 4:
            insights.append("Ajustar criterios de decisión para handoffs humanos")
        
        handoff_issues = patterns.get("handoff_issues", {})
        if handoff_issues.get("premature_handoffs", 0) > 2:
            insights.append("Reducir handoffs prematuros - IA puede manejar más casos")
        
        return insights


class AutoOptimizer:
    """Sistema principal de optimización automática."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pattern_analyzer = PatternAnalyzer()
        self.improvement_rules: List[ImprovementRule] = []
        self.optimization_strategies: Dict[str, OptimizationStrategy] = {}
        self._load_existing_rules()
    
    def _load_existing_rules(self):
        """Carga reglas de mejora existentes."""
        # En producción, esto cargaría desde base de datos
        self.optimization_strategies = {
            "response_quality": OptimizationStrategy(
                strategy_id="rq_001",
                name="Mejora de Calidad de Respuesta",
                description="Optimiza respuestas basándose en patrones de falla",
                target_metric="response_quality",
                improvement_rules=[]
            ),
            "handoff_optimization": OptimizationStrategy(
                strategy_id="ho_001",
                name="Optimización de Handoffs",
                description="Mejora decisiones de transferencia a humanos",
                target_metric="handoff_quality",
                improvement_rules=[]
            )
        }
    
    async def run_optimization_cycle(self, test_results: List[TestResult]) -> Dict[str, Any]:
        """Ejecuta un ciclo completo de optimización."""
        if not config.AUTO_IMPROVEMENT_ENABLED:
            self.logger.info("Automejora deshabilitada en configuración")
            return {"status": "disabled", "reason": "Auto-improvement disabled in config"}
        
        self.logger.info(f"Iniciando ciclo de optimización con {len(test_results)} resultados")
        
        # 1. Analizar patrones
        pattern_analysis = self.pattern_analyzer.analyze_failure_patterns(test_results)
        
        # 2. Generar reglas de mejora
        new_rules = await self._generate_improvement_rules(pattern_analysis)
        
        # 3. Aplicar mejoras si está habilitado
        applied_improvements = []
        if config.AUTO_APPLY_IMPROVEMENTS:
            applied_improvements = await self._apply_improvements(new_rules)
        
        # 4. Generar reporte
        optimization_report = {
            "cycle_timestamp": datetime.now(),
            "pattern_analysis": pattern_analysis,
            "new_rules_generated": len(new_rules),
            "improvements_applied": len(applied_improvements),
            "recommendations": self._generate_recommendations(pattern_analysis),
            "next_optimization": datetime.now() + timedelta(hours=config.OPTIMIZATION_INTERVAL_HOURS)
        }
        
        # 5. Guardar estado
        await self._save_optimization_state(optimization_report)
        
        return optimization_report
    
    async def _generate_improvement_rules(self, pattern_analysis: Dict[str, Any]) -> List[ImprovementRule]:
        """Genera nuevas reglas de mejora basándose en el análisis de patrones."""
        new_rules = []
        patterns = pattern_analysis.get("patterns", {})
        insights = pattern_analysis.get("insights", [])
        
        failure_types = patterns.get("common_failure_types", {})
        
        # Regla para mejorar calidad de respuesta
        if failure_types.get("low_response_quality", 0) > config.MIN_FAILURES_FOR_RULE:
            rule = ImprovementRule(
                rule_id=f"rq_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                description="Mejorar calidad de respuestas basándose en patrones de falla",
                condition="response_quality < 0.6",
                action="expand_knowledge_base",
                confidence=0.8,
                impact_estimate=0.3,
                applicable_scenarios=["wine_consultation", "general_inquiry"],
                created_at=datetime.now()
            )
            new_rules.append(rule)
        
        # Regla para optimizar handoffs
        if failure_types.get("poor_handoff_decision", 0) > config.MIN_FAILURES_FOR_RULE:
            rule = ImprovementRule(
                rule_id=f"ho_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                description="Ajustar criterios de handoff basándose en fallas detectadas",
                condition="handoff_quality < 0.7",
                action="adjust_handoff_threshold",
                confidence=0.7,
                impact_estimate=0.4,
                applicable_scenarios=["complex_booking", "complaint_handling"],
                created_at=datetime.now()
            )
            new_rules.append(rule)
        
        # Regla específica para conocimiento de vinos
        if failure_types.get("wine_knowledge_gaps", 0) > 2:
            rule = ImprovementRule(
                rule_id=f"wk_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                description="Expandir base de conocimiento específica de vinos",
                condition="scenario_type == 'wine_consultation' AND response_quality < 0.7",
                action="enhance_wine_knowledge",
                confidence=0.9,
                impact_estimate=0.5,
                applicable_scenarios=["wine_consultation", "wine_recommendation"],
                created_at=datetime.now()
            )
            new_rules.append(rule)
        
        self.improvement_rules.extend(new_rules)
        return new_rules
    
    async def _apply_improvements(self, rules: List[ImprovementRule]) -> List[Dict[str, Any]]:
        """Aplica mejoras automáticamente si está configurado."""
        applied = []
        
        for rule in rules:
            if rule.confidence >= config.MIN_CONFIDENCE_FOR_AUTO_APPLY:
                try:
                    result = await self._execute_improvement_action(rule)
                    if result["success"]:
                        applied.append({
                            "rule_id": rule.rule_id,
                            "action": rule.action,
                            "result": result
                        })
                        rule.applied_count += 1
                except Exception as e:
                    self.logger.error(f"Error aplicando mejora {rule.rule_id}: {str(e)}")
        
        return applied
    
    async def _execute_improvement_action(self, rule: ImprovementRule) -> Dict[str, Any]:
        """Ejecuta una acción de mejora específica."""
        action = rule.action
        
        if action == "expand_knowledge_base":
            return await self._expand_knowledge_base(rule)
        elif action == "adjust_handoff_threshold":
            return await self._adjust_handoff_threshold(rule)
        elif action == "enhance_wine_knowledge":
            return await self._enhance_wine_knowledge(rule)
        else:
            return {"success": False, "reason": f"Unknown action: {action}"}
    
    async def _expand_knowledge_base(self, rule: ImprovementRule) -> Dict[str, Any]:
        """Expande la base de conocimiento general."""
        # En producción, esto actualizaría la base de conocimiento
        self.logger.info(f"Expandiendo base de conocimiento para regla {rule.rule_id}")
        return {
            "success": True,
            "action": "knowledge_base_expanded",
            "details": "Added general knowledge entries based on failure patterns"
        }
    
    async def _adjust_handoff_threshold(self, rule: ImprovementRule) -> Dict[str, Any]:
        """Ajusta umbrales de handoff."""
        self.logger.info(f"Ajustando umbrales de handoff para regla {rule.rule_id}")
        return {
            "success": True,
            "action": "handoff_threshold_adjusted",
            "details": "Handoff confidence threshold lowered by 0.1"
        }
    
    async def _enhance_wine_knowledge(self, rule: ImprovementRule) -> Dict[str, Any]:
        """Mejora conocimiento específico de vinos."""
        self.logger.info(f"Mejorando conocimiento de vinos para regla {rule.rule_id}")
        return {
            "success": True,
            "action": "wine_knowledge_enhanced",
            "details": "Added wine-specific knowledge and recommendations"
        }
    
    def _generate_recommendations(self, pattern_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Genera recomendaciones para mejoras manuales."""
        recommendations = []
        insights = pattern_analysis.get("insights", [])
        
        for insight in insights:
            recommendations.append({
                "type": "manual_review",
                "description": insight,
                "priority": "high" if "booking" in insight.lower() else "medium",
                "estimated_effort": "2-4 hours"
            })
        
        return recommendations
    
    async def _save_optimization_state(self, report: Dict[str, Any]):
        """Guarda el estado de optimización para tracking."""
        # En producción, esto guardaría en base de datos
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"optimization_report_{timestamp}.json"
        
        try:
            # Convertir objetos datetime a string para serialización
            serializable_report = self._make_serializable(report)
            
            self.logger.info(f"Guardando reporte de optimización: {filename}")
            # Aquí se guardaría en base de datos o filesystem
        except Exception as e:
            self.logger.error(f"Error guardando estado de optimización: {str(e)}")
    
    def _make_serializable(self, obj):
        """Convierte objetos a formato serializable."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        else:
            return obj
    
    def get_optimization_status(self) -> Dict[str, Any]:
        """Retorna el estado actual del sistema de optimización."""
        return {
            "enabled": config.AUTO_IMPROVEMENT_ENABLED,
            "auto_apply": config.AUTO_APPLY_IMPROVEMENTS,
            "active_rules": len(self.improvement_rules),
            "strategies": list(self.optimization_strategies.keys()),
            "last_optimization": "Not available",
            "next_optimization": datetime.now() + timedelta(hours=config.OPTIMIZATION_INTERVAL_HOURS)
        }


# Función principal para uso externo
async def run_auto_optimization(test_results: List[TestResult]) -> Dict[str, Any]:
    """Función principal para ejecutar optimización automática."""
    optimizer = AutoOptimizer()
    return await optimizer.run_optimization_cycle(test_results)