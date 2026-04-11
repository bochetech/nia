"""
Conversation evaluators for assessing response quality, handoff decisions, and overall performance
"""
import asyncio
from typing import List, Dict, Optional, Tuple
import re
from datetime import datetime
import openai
from ..models import ConversationResult, EvaluationResult, ConversationTurn, HandoffEvent
from ..config import testing_config


class BaseEvaluator:
    """Base class for all conversation evaluators"""
    
    def __init__(self):
        self.model = testing_config.evaluation_model
        self.temperature = testing_config.evaluation_temperature
        
    async def evaluate(self, conversation: ConversationResult, scenario_definition: dict) -> EvaluationResult:
        """Override in subclasses"""
        raise NotImplementedError
        

class ResponseQualityEvaluator(BaseEvaluator):
    """Evaluates the quality of individual responses"""
    
    async def evaluate(self, conversation: ConversationResult, scenario_definition: dict) -> EvaluationResult:
        """Evaluate response quality using LLM-based analysis"""
        
        relevance_scores = []
        accuracy_scores = []
        tone_scores = []
        
        for i, turn in enumerate(conversation.turns):
            if turn.role.value == "assistant":
                # Evaluate this assistant response
                scores = await self._evaluate_turn(turn, conversation.turns[:i+1], scenario_definition)
                relevance_scores.append(scores["relevance"])
                accuracy_scores.append(scores["accuracy"])
                tone_scores.append(scores["tone"])
        
        # Calculate overall scores
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        avg_accuracy = sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0
        avg_tone = sum(tone_scores) / len(tone_scores) if tone_scores else 0
        
        # Overall response quality (weighted average)
        response_quality = (avg_relevance * 0.4 + avg_accuracy * 0.4 + avg_tone * 0.2)
        
        # Determine strengths and weaknesses
        strengths, weaknesses, improvements = self._analyze_patterns(relevance_scores, accuracy_scores, tone_scores)
        
        return EvaluationResult(
            conversation_id=conversation.conversation_id,
            scenario_name=conversation.scenario_name,
            overall_score=response_quality,
            success=response_quality >= scenario_definition.get("min_response_quality", 0.8),
            response_quality_score=response_quality,
            relevance_scores=relevance_scores,
            accuracy_scores=accuracy_scores,
            tone_scores=tone_scores,
            strengths=strengths,
            weaknesses=weaknesses,
            improvement_suggestions=improvements
        )
    
    async def _evaluate_turn(self, turn: ConversationTurn, conversation_context: List[ConversationTurn], scenario_def: dict) -> Dict[str, float]:
        """Evaluate a single assistant turn"""
        
        # Build context for evaluation
        context = self._build_context_string(conversation_context)
        response = turn.content
        
        evaluation_prompt = f"""
        Evalúa esta respuesta del asistente de enoturismo en una escala de 0.0 a 1.0:

        CONTEXTO DE LA CONVERSACIÓN:
        {context}

        RESPUESTA A EVALUAR:
        {response}

        ESCENARIO: {scenario_def.get('description', 'N/A')}
        CATEGORÍA: {scenario_def.get('category', 'N/A')}

        Evalúa en estas dimensiones:

        1. RELEVANCIA (0.0-1.0): ¿Qué tan relevante es la respuesta al contexto y pregunta del usuario?
        2. PRECISIÓN (0.0-1.0): ¿Es la información factualmente correcta y específica para enoturismo?
        3. TONO (0.0-1.0): ¿Es el tono apropiado, profesional y acorde a la marca Concha y Toro?

        Responde SOLO en este formato JSON:
        {{
            "relevance": 0.X,
            "accuracy": 0.X, 
            "tone": 0.X,
            "reasoning": "Breve explicación de los puntajes"
        }}
        """
        
        try:
            response = await self._call_evaluation_llm(evaluation_prompt)
            # Parse JSON response
            import json
            scores = json.loads(response)
            return {
                "relevance": float(scores.get("relevance", 0.5)),
                "accuracy": float(scores.get("accuracy", 0.5)),
                "tone": float(scores.get("tone", 0.5))
            }
        except Exception as e:
            # Fallback scoring if LLM fails
            return {"relevance": 0.5, "accuracy": 0.5, "tone": 0.5}
    
    def _build_context_string(self, turns: List[ConversationTurn]) -> str:
        """Build readable context from conversation turns"""
        context_parts = []
        for turn in turns:
            role = "Usuario" if turn.role.value == "user" else "Asistente"
            context_parts.append(f"{role}: {turn.content}")
        return "\n".join(context_parts)
    
    def _analyze_patterns(self, relevance: List[float], accuracy: List[float], tone: List[float]) -> Tuple[List[str], List[str], List[str]]:
        """Analyze scoring patterns to identify strengths and weaknesses"""
        
        strengths = []
        weaknesses = []
        improvements = []
        
        avg_relevance = sum(relevance) / len(relevance) if relevance else 0
        avg_accuracy = sum(accuracy) / len(accuracy) if accuracy else 0
        avg_tone = sum(tone) / len(tone) if tone else 0
        
        if avg_relevance >= 0.85:
            strengths.append("Excelente relevancia de respuestas")
        elif avg_relevance < 0.7:
            weaknesses.append("Respuestas poco relevantes al contexto")
            improvements.append("Mejorar comprensión del contexto del usuario")
            
        if avg_accuracy >= 0.85:
            strengths.append("Alta precisión en información")
        elif avg_accuracy < 0.7:
            weaknesses.append("Información imprecisa o genérica")
            improvements.append("Actualizar knowledge base con datos específicos")
            
        if avg_tone >= 0.85:
            strengths.append("Tono consistente con la marca")
        elif avg_tone < 0.7:
            weaknesses.append("Tono inconsistente o inapropiado")
            improvements.append("Refinar prompt para mantener tono de marca")
        
        # Pattern analysis
        if len(relevance) > 1:
            if relevance[-1] < relevance[0] - 0.2:
                weaknesses.append("Degradación de relevancia durante la conversación")
                improvements.append("Mejorar mantenimiento de contexto en conversaciones largas")
        
        return strengths, weaknesses, improvements
    
    async def _call_evaluation_llm(self, prompt: str) -> str:
        """Call LLM for evaluation"""
        try:
            client = openai.AsyncOpenAI()
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un evaluador experto de conversaciones de IA para enoturismo. Proporciona evaluaciones precisas y constructivas."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            return '{"relevance": 0.5, "accuracy": 0.5, "tone": 0.5, "reasoning": "Error en evaluación LLM"}'


class HandoffQualityEvaluator(BaseEvaluator):
    """Evaluates the quality of handoff decisions and context preservation"""
    
    async def evaluate(self, conversation: ConversationResult, scenario_definition: dict) -> EvaluationResult:
        """Evaluate handoff quality"""
        
        if not conversation.handoff_event:
            # No handoff occurred
            expected_handoff = scenario_definition.get("expected_handoff_type")
            if expected_handoff:
                # Should have triggered handoff but didn't
                return self._create_missed_handoff_evaluation(conversation, scenario_definition)
            else:
                # Correctly no handoff
                return self._create_no_handoff_evaluation(conversation, scenario_definition)
        
        # Handoff occurred - evaluate quality
        return await self._evaluate_handoff_quality(conversation, scenario_definition)
    
    async def _evaluate_handoff_quality(self, conversation: ConversationResult, scenario_def: dict) -> EvaluationResult:
        """Evaluate an actual handoff event"""
        
        handoff = conversation.handoff_event
        expected_type = scenario_def.get("expected_handoff_type")
        
        # Check if handoff type is appropriate
        type_appropriate = (expected_type is None) or (handoff.handoff_type == expected_type)
        
        # Evaluate timing
        timing_score = self._evaluate_handoff_timing(conversation, handoff)
        
        # Evaluate context preservation
        context_score = await self._evaluate_context_preservation(conversation, handoff)
        
        # Evaluate trigger appropriateness
        trigger_score = self._evaluate_trigger_appropriateness(conversation, handoff, scenario_def)
        
        # Overall handoff quality score
        handoff_quality = (
            (1.0 if type_appropriate else 0.3) * 0.3 +
            timing_score * 0.25 +
            context_score * 0.25 + 
            trigger_score * 0.2
        )
        
        # Analysis
        strengths, weaknesses, improvements = self._analyze_handoff_quality(
            type_appropriate, timing_score, context_score, trigger_score, handoff
        )
        
        return EvaluationResult(
            conversation_id=conversation.conversation_id,
            scenario_name=conversation.scenario_name,
            overall_score=handoff_quality,
            success=handoff_quality >= 0.8,
            handoff_quality_score=handoff_quality,
            strengths=strengths,
            weaknesses=weaknesses,
            improvement_suggestions=improvements
        )
    
    def _evaluate_handoff_timing(self, conversation: ConversationResult, handoff: HandoffEvent) -> float:
        """Evaluate if handoff happened at appropriate time"""
        
        total_turns = len(conversation.turns)
        handoff_turn = handoff.turn_number
        
        # Too early (< 2 turns) = not enough information gathered
        if handoff_turn < 2:
            return 0.3
        
        # Too late (> 8 turns) = user frustration likely  
        if handoff_turn > 8:
            return 0.6
            
        # Sweet spot: 2-6 turns
        if 2 <= handoff_turn <= 6:
            return 1.0
            
        # Acceptable: 7-8 turns
        return 0.8
    
    async def _evaluate_context_preservation(self, conversation: ConversationResult, handoff: HandoffEvent) -> float:
        """Evaluate how well context was preserved in handoff"""
        
        # Extract key information from conversation
        conversation_text = "\n".join([f"{turn.role.value}: {turn.content}" for turn in conversation.turns])
        handoff_context = str(handoff.context_data)
        
        evaluation_prompt = f"""
        Evalúa qué tan bien se preservó el contexto en esta derivación de conversación:

        CONVERSACIÓN COMPLETA:
        {conversation_text}

        CONTEXTO TRANSFERIDO EN HANDOFF:
        {handoff_context}

        RAZÓN DE DERIVACIÓN: {handoff.trigger_reason}

        En una escala de 0.0 a 1.0, evalúa:
        - ¿Se capturó la información clave del usuario?
        - ¿Se preservaron los detalles importantes?
        - ¿Es suficiente para que el agente humano continúe efectivamente?

        Responde solo con un número entre 0.0 y 1.0:
        """
        
        try:
            response = await self._call_evaluation_llm(evaluation_prompt)
            score = float(re.search(r'(\d+\.?\d*)', response).group(1))
            return min(max(score, 0.0), 1.0)
        except:
            return 0.7  # Default middle score if evaluation fails
    
    def _evaluate_trigger_appropriateness(self, conversation: ConversationResult, handoff: HandoffEvent, scenario_def: dict) -> float:
        """Evaluate if handoff was triggered for appropriate reasons"""
        
        trigger_keywords = scenario_def.get("handoff_trigger_keywords", [])
        conversation_text = " ".join([turn.content.lower() for turn in conversation.turns if turn.role.value == "user"])
        
        # Check if expected keywords appeared
        keywords_found = sum(1 for keyword in trigger_keywords if keyword.lower() in conversation_text)
        keyword_score = keywords_found / len(trigger_keywords) if trigger_keywords else 1.0
        
        # Check against common handoff scenarios
        reason_lower = handoff.trigger_reason.lower()
        appropriate_reasons = [
            "large group", "corporate", "complaint", "technical issue",
            "complex request", "billing", "escalation", "specialized service"
        ]
        
        reason_appropriate = any(reason in reason_lower for reason in appropriate_reasons)
        reason_score = 1.0 if reason_appropriate else 0.5
        
        return (keyword_score * 0.6 + reason_score * 0.4)
    
    def _analyze_handoff_quality(self, type_appropriate: bool, timing_score: float, 
                                context_score: float, trigger_score: float, handoff: HandoffEvent) -> Tuple[List[str], List[str], List[str]]:
        """Analyze handoff quality patterns"""
        
        strengths = []
        weaknesses = []
        improvements = []
        
        if type_appropriate:
            strengths.append("Derivación al departamento correcto")
        else:
            weaknesses.append("Departamento de derivación incorrecto")
            improvements.append("Revisar lógica de routing por tipo de consulta")
        
        if timing_score >= 0.8:
            strengths.append("Timing apropiado de derivación")
        else:
            weaknesses.append("Timing subóptimo de derivación")
            if timing_score < 0.5:
                improvements.append("Ajustar umbrales de detección de complejidad")
        
        if context_score >= 0.8:
            strengths.append("Excelente preservación de contexto")
        else:
            weaknesses.append("Pérdida de contexto en derivación")
            improvements.append("Mejorar captura y transferencia de información clave")
        
        if trigger_score >= 0.8:
            strengths.append("Razones de derivación apropiadas")
        else:
            weaknesses.append("Derivación por razones cuestionables")
            improvements.append("Refinar criterios de detección de casos complejos")
            
        return strengths, weaknesses, improvements
    
    def _create_missed_handoff_evaluation(self, conversation: ConversationResult, scenario_def: dict) -> EvaluationResult:
        """Create evaluation for missed handoff scenario"""
        return EvaluationResult(
            conversation_id=conversation.conversation_id,
            scenario_name=conversation.scenario_name,
            overall_score=0.3,
            success=False,
            handoff_quality_score=0.0,
            weaknesses=["Falló en detectar necesidad de derivación"],
            improvement_suggestions=["Mejorar detección de casos que requieren atención humana"]
        )
    
    def _create_no_handoff_evaluation(self, conversation: ConversationResult, scenario_def: dict) -> EvaluationResult:
        """Create evaluation for correctly handled conversation without handoff"""
        return EvaluationResult(
            conversation_id=conversation.conversation_id,
            scenario_name=conversation.scenario_name,
            overall_score=1.0,
            success=True,
            handoff_quality_score=1.0,
            strengths=["Resolvió correctamente sin necesidad de derivación"]
        )


class EntityExtractionEvaluator(BaseEvaluator):
    """Evaluates how well entities were extracted from conversations"""
    
    async def evaluate(self, conversation: ConversationResult, scenario_definition: dict) -> EvaluationResult:
        """Evaluate entity extraction accuracy"""
        
        expected_entities = scenario_definition.get("expected_entities", {})
        extracted_entities = conversation.entities_extracted
        
        if not expected_entities:
            return EvaluationResult(
                conversation_id=conversation.conversation_id,
                scenario_name=conversation.scenario_name, 
                overall_score=1.0,
                success=True,
                entity_extraction_score=1.0,
                strengths=["No entity extraction required"]
            )
        
        # Calculate precision and recall for entities
        precision, recall, f1_score = self._calculate_entity_metrics(expected_entities, extracted_entities)
        
        # Entity-specific analysis
        entity_analysis = self._analyze_entity_extraction(expected_entities, extracted_entities)
        
        success = f1_score >= 0.8
        
        return EvaluationResult(
            conversation_id=conversation.conversation_id,
            scenario_name=conversation.scenario_name,
            overall_score=f1_score,
            success=success,
            entity_extraction_score=f1_score,
            strengths=entity_analysis["strengths"],
            weaknesses=entity_analysis["weaknesses"], 
            improvement_suggestions=entity_analysis["improvements"]
        )
    
    def _calculate_entity_metrics(self, expected: Dict, extracted: Dict) -> Tuple[float, float, float]:
        """Calculate precision, recall, and F1 for entity extraction"""
        
        if not expected:
            return 1.0, 1.0, 1.0
            
        # Count correct extractions
        correct = 0
        total_expected = len(expected)
        total_extracted = len(extracted)
        
        for key, expected_value in expected.items():
            if key in extracted:
                extracted_value = extracted[key]
                # Fuzzy matching for strings
                if self._values_match(expected_value, extracted_value):
                    correct += 1
        
        # Calculate metrics
        precision = correct / total_extracted if total_extracted > 0 else 0
        recall = correct / total_expected if total_expected > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return precision, recall, f1_score
    
    def _values_match(self, expected, extracted) -> bool:
        """Check if extracted value matches expected value"""
        
        # Exact match
        if expected == extracted:
            return True
            
        # String similarity for text values
        if isinstance(expected, str) and isinstance(extracted, str):
            return self._string_similarity(expected.lower(), extracted.lower()) >= 0.8
            
        # Numeric tolerance  
        if isinstance(expected, (int, float)) and isinstance(extracted, (int, float)):
            return abs(expected - extracted) <= 1
            
        return False
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity using simple overlap"""
        words1 = set(s1.split())
        words2 = set(s2.split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
            
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def _analyze_entity_extraction(self, expected: Dict, extracted: Dict) -> Dict[str, List[str]]:
        """Analyze entity extraction performance"""
        
        strengths = []
        weaknesses = []
        improvements = []
        
        for key, expected_value in expected.items():
            if key in extracted:
                if self._values_match(expected_value, extracted[key]):
                    strengths.append(f"Correctamente extrajo {key}")
                else:
                    weaknesses.append(f"Valor incorrecto para {key}")
                    improvements.append(f"Mejorar extracción de {key}")
            else:
                weaknesses.append(f"No extrajo {key}")
                improvements.append(f"Implementar detección de {key}")
        
        # Check for over-extraction
        for key in extracted:
            if key not in expected:
                weaknesses.append(f"Extrajo {key} innecesariamente")
        
        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "improvements": improvements
        }


class ConversationFlowEvaluator(BaseEvaluator):
    """Evaluates the overall flow and natural progression of conversation"""
    
    async def evaluate(self, conversation: ConversationResult, scenario_definition: dict) -> EvaluationResult:
        """Evaluate conversation flow quality"""
        
        expected_behaviors = scenario_definition.get("expected_assistant_behaviors", [])
        
        if not expected_behaviors:
            return EvaluationResult(
                conversation_id=conversation.conversation_id,
                scenario_name=conversation.scenario_name,
                overall_score=0.8,
                success=True,
                conversation_flow_score=0.8,
                strengths=["No specific flow requirements"]
            )
        
        flow_scores = []
        behavior_analysis = []
        
        # Evaluate each expected behavior
        for i, expected_behavior in enumerate(expected_behaviors):
            turn_number = expected_behavior.get("turn", i + 1)
            score, analysis = await self._evaluate_behavior_compliance(
                conversation, turn_number, expected_behavior
            )
            flow_scores.append(score)
            behavior_analysis.append(analysis)
        
        # Calculate overall flow score
        overall_flow_score = sum(flow_scores) / len(flow_scores) if flow_scores else 0.8
        
        # Aggregate analysis
        all_strengths = [item for sublist in [a["strengths"] for a in behavior_analysis] for item in sublist]
        all_weaknesses = [item for sublist in [a["weaknesses"] for a in behavior_analysis] for item in sublist] 
        all_improvements = [item for sublist in [a["improvements"] for a in behavior_analysis] for item in sublist]
        
        return EvaluationResult(
            conversation_id=conversation.conversation_id,
            scenario_name=conversation.scenario_name,
            overall_score=overall_flow_score,
            success=overall_flow_score >= 0.75,
            conversation_flow_score=overall_flow_score,
            strengths=all_strengths,
            weaknesses=all_weaknesses,
            improvement_suggestions=all_improvements
        )
    
    async def _evaluate_behavior_compliance(self, conversation: ConversationResult, 
                                          turn_number: int, expected_behavior: Dict) -> Tuple[float, Dict]:
        """Evaluate compliance with expected behavior for a specific turn"""
        
        # Find the corresponding assistant turn
        assistant_turns = [turn for turn in conversation.turns if turn.role.value == "assistant"]
        
        if turn_number > len(assistant_turns):
            return 0.0, {
                "strengths": [],
                "weaknesses": ["Conversación terminó antes del turno esperado"],
                "improvements": ["Extender duración de conversación"]
            }
        
        target_turn = assistant_turns[turn_number - 1]
        response_content = target_turn.content.lower()
        
        # Check various compliance criteria
        compliance_scores = []
        analysis = {"strengths": [], "weaknesses": [], "improvements": []}
        
        # Should mention keywords
        should_mention = expected_behavior.get("should_mention", [])
        mention_score = self._check_mentions(response_content, should_mention)
        compliance_scores.append(mention_score)
        
        if mention_score >= 0.8:
            analysis["strengths"].append("Mencionó elementos clave esperados")
        else:
            analysis["weaknesses"].append("No mencionó elementos importantes")
            analysis["improvements"].append("Incluir keywords relevantes en respuesta")
        
        # Should ask for information
        should_ask_for = expected_behavior.get("should_ask_for", [])
        ask_score = self._check_questions(response_content, should_ask_for)
        compliance_scores.append(ask_score)
        
        if ask_score >= 0.8:
            analysis["strengths"].append("Hizo las preguntas apropiadas")
        else:
            analysis["weaknesses"].append("No recopiló información necesaria")
            analysis["improvements"].append("Mejorar gathering de información clave")
        
        # Should not do certain things
        should_not = expected_behavior.get("should_not", [])
        avoid_score = self._check_avoidance(response_content, should_not)
        compliance_scores.append(avoid_score)
        
        if avoid_score < 0.8:
            analysis["weaknesses"].append("Hizo algo que debería evitar")
            analysis["improvements"].append("Revisar restricciones de comportamiento")
        
        # Tone check
        expected_tone = expected_behavior.get("tone")
        if expected_tone:
            tone_score = await self._check_tone(target_turn.content, expected_tone)
            compliance_scores.append(tone_score)
            
            if tone_score >= 0.8:
                analysis["strengths"].append(f"Tono {expected_tone} apropiado")
            else:
                analysis["weaknesses"].append(f"Tono no {expected_tone}")
                analysis["improvements"].append(f"Ajustar prompt para tono {expected_tone}")
        
        # Calculate average compliance
        avg_compliance = sum(compliance_scores) / len(compliance_scores) if compliance_scores else 0.5
        
        return avg_compliance, analysis
    
    def _check_mentions(self, response: str, should_mention: List[str]) -> float:
        """Check if response mentions expected keywords"""
        if not should_mention:
            return 1.0
            
        mentions_found = sum(1 for keyword in should_mention if keyword.lower() in response)
        return mentions_found / len(should_mention)
    
    def _check_questions(self, response: str, should_ask_for: List[str]) -> float:
        """Check if response asks for expected information"""
        if not should_ask_for:
            return 1.0
            
        # Simple heuristic: look for question marks and ask-related keywords
        has_questions = "?" in response or any(word in response for word in ["cuál", "qué", "cómo", "cuándo", "dónde"])
        
        if not has_questions:
            return 0.0
            
        # More sophisticated: check if asking for specific information
        asks_found = sum(1 for ask_item in should_ask_for 
                        if any(keyword in response for keyword in ask_item.lower().split()))
        
        return min(1.0, asks_found / len(should_ask_for) + 0.3)  # Bonus for having questions at all
    
    def _check_avoidance(self, response: str, should_not: List[str]) -> float:
        """Check if response avoids doing prohibited things"""
        if not should_not:
            return 1.0
            
        violations = sum(1 for prohibited in should_not if prohibited.lower() in response)
        return max(0.0, 1.0 - (violations / len(should_not)))
    
    async def _check_tone(self, response: str, expected_tone: str) -> float:
        """Check if response has expected tone"""
        
        tone_prompt = f"""
        Evalúa si esta respuesta tiene un tono {expected_tone}:
        
        RESPUESTA: {response}
        
        TONO ESPERADO: {expected_tone}
        
        Responde solo con un número de 0.0 a 1.0 indicando qué tan bien coincide el tono:
        """
        
        try:
            response = await self._call_evaluation_llm(tone_prompt)
            score = float(re.search(r'(\d+\.?\d*)', response).group(1))
            return min(max(score, 0.0), 1.0)
        except:
            return 0.7  # Default score if evaluation fails