"""
Módulo de automejora para el framework de testing conversacional.
"""

from .auto_optimizer import (
    AutoOptimizer,
    PatternAnalyzer,
    ImprovementRule,
    OptimizationStrategy,
    run_auto_optimization
)

__all__ = [
    'AutoOptimizer',
    'PatternAnalyzer', 
    'ImprovementRule',
    'OptimizationStrategy',
    'run_auto_optimization'
]