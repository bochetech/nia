"""
Flujo de transiciones e intents default del orquestador NIA.

Re-exporta desde shared.models.flow_defaults para compatibilidad
con imports existentes dentro del orchestrator.
"""

from shared.models.flow_defaults import (  # noqa: F401  re-export
    DEFAULT_INTENTS,
    DEFAULT_SKILLS,
    DEFAULT_TRANSITIONS,
)
