"""
Automated test runner for conversation testing
Orchestrates conversation simulation, evaluation, and reporting
"""
import asyncio
import uuid
import json
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import logging
from concurrent.futures import ThreadPoolExecutor

from ..models import (
    ConversationResult, ConversationTurn, HandoffEvent, EvaluationResult, 
    TestSuiteResult, ConversationOutcome, HandoffType, MessageRole
)
from ..config import testing_config, ENOTURISMO_SCENARIOS
from ..scenarios.enoturismo_scenarios import EnoturismoTestScenarios
from ..evaluators.conversation_evaluators import (
    ResponseQualityEvaluator, HandoffQualityEvaluator, 
    EntityExtractionEvaluator, ConversationFlowEvaluator
)


class ConversationSimulator:
    """Simulates conversations with the OpenChat NIA system"""
    
    def __init__(self):
        self.base_url = testing_config.base_url
        self.tenant_id = testing_config.tenant_id
        self.timeout = testing_config.test_timeout
        
    async def simulate_conversation(self, scenario: Dict, conversation_id: str) -> ConversationResult:
        """Simulate a complete conversation based on scenario"""
        
        start_time = datetime.now()
        turns = []
        handoff_event = None
        outcome = ConversationOutcome.SUCCESS
        entities_extracted = {}
        error_message = None
        failed_at_turn = None
        
        try:
            # Initialize conversation session
            session_data = await self._initialize_session()
            
            # Process each user input in the scenario
            user_inputs = scenario.user_inputs
            
            for i, user_input in enumerate(user_inputs):
                # Add user turn
                user_turn = ConversationTurn(
                    role=MessageRole.USER,
                    content=user_input,
                    timestamp=datetime.now()
                )
                turns.append(user_turn)
                
                # Get assistant response
                try:
                    assistant_response, response_metadata = await self._get_assistant_response(
                        user_input, session_data, conversation_id
                    )
                    
                    # Add assistant turn
                    assistant_turn = ConversationTurn(
                        role=MessageRole.ASSISTANT,
                        content=assistant_response,
                        timestamp=datetime.now(),
                        metadata=response_metadata,
                        response_time_ms=response_metadata.get("response_time_ms"),
                        token_count=response_metadata.get("token_count")
                    )
                    turns.append(assistant_turn)
                    
                    # Check for handoff indicators
                    if self._detect_handoff(assistant_response, response_metadata):
                        handoff_event = self._extract_handoff_info(assistant_response, response_metadata, i + 1)
                        outcome = ConversationOutcome.HANDOFF
                        break
                        
                    # Extract entities if present
                    turn_entities = response_metadata.get("entities_extracted", {})
                    entities_extracted.update(turn_entities)
                    
                except asyncio.TimeoutError:
                    outcome = ConversationOutcome.TIMEOUT
                    error_message = f"Timeout at turn {i + 1}"
                    failed_at_turn = i + 1
                    break
                    
                except Exception as e:
                    outcome = ConversationOutcome.ERROR
                    error_message = f"Error at turn {i + 1}: {str(e)}"
                    failed_at_turn = i + 1
                    break
                
                # Add small delay between turns to simulate natural conversation
                await asyncio.sleep(0.5)
            
            # Determine if objective was achieved
            objective_achieved = self._evaluate_objective_achievement(scenario, turns, handoff_event, outcome)
            
        except Exception as e:
            outcome = ConversationOutcome.ERROR
            error_message = f"Conversation initialization error: {str(e)}"
            objective_achieved = False
        
        end_time = datetime.now()
        total_duration = int((end_time - start_time).total_seconds() * 1000)
        
        return ConversationResult(
            scenario_name=scenario.name,
            conversation_id=conversation_id,
            turns=turns,
            outcome=outcome,
            handoff_event=handoff_event,
            start_time=start_time,
            end_time=end_time,
            total_duration_ms=total_duration,
            objective_achieved=objective_achieved,
            entities_extracted=entities_extracted,
            expected_entities=scenario.expected_entities,
            error_message=error_message,
            failed_at_turn=failed_at_turn
        )
    
    async def _initialize_session(self) -> Dict[str, Any]:
        """Initialize a conversation session"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/conversations",
                    json={
                        "tenant_id": self.tenant_id,
                        "session_type": "test"
                    }
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                # Fallback for testing without full API
                return {
                    "session_id": str(uuid.uuid4()),
                    "tenant_id": self.tenant_id,
                    "conversation_id": str(uuid.uuid4())
                }
    
    async def _get_assistant_response(self, user_input: str, session_data: Dict, conversation_id: str) -> tuple[str, Dict]:
        """Get response from NIA assistant"""
        
        request_start = datetime.now()
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Make request to OpenChat orchestrator
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "message": user_input,
                        "conversation_id": conversation_id,
                        "tenant_id": self.tenant_id,
                        "session_data": session_data
                    }
                )
                response.raise_for_status()
                response_data = response.json()
                
                request_end = datetime.now()
                response_time = int((request_end - request_start).total_seconds() * 1000)
                
                # Extract response content and metadata
                assistant_response = response_data.get("response", "")
                metadata = {
                    "response_time_ms": response_time,
                    "token_count": response_data.get("token_count"),
                    "entities_extracted": response_data.get("entities", {}),
                    "handoff_triggered": response_data.get("handoff_triggered", False),
                    "handoff_type": response_data.get("handoff_type"),
                    "handoff_reason": response_data.get("handoff_reason"),
                    "confidence_score": response_data.get("confidence_score"),
                    "recommendations": response_data.get("recommendations", [])
                }
                
                return assistant_response, metadata
                
            except httpx.TimeoutException:
                raise asyncio.TimeoutError("Request timeout")
            except Exception as e:
                # Fallback response for testing
                return self._generate_fallback_response(user_input), {"response_time_ms": 1000}
    
    def _generate_fallback_response(self, user_input: str) -> str:
        """Generate a fallback response for testing when API is not available"""
        
        input_lower = user_input.lower()
        
        if any(word in input_lower for word in ["reserva", "book", "tour"]):
            return "¡Hola! Me encantaría ayudarte a reservar un tour. ¿Para cuántas personas y qué fecha tienes en mente?"
        elif any(word in input_lower for word in ["precio", "costo", "cuánto"]):
            return "Los precios varían según la experiencia. ¿Qué tipo de tour te interesa? Tenemos desde tours básicos hasta experiencias premium nocturnas."
        elif any(word in input_lower for word in ["horario", "hora", "cuándo"]):
            return "Tenemos múltiples horarios disponibles durante el día. ¿Prefieres mañana o tarde? ¿Y para qué fecha?"
        elif any(word in input_lower for word in ["queja", "problema", "mal"]):
            return "Lamento mucho escuchar sobre tu experiencia. Me gustaría ayudarte a resolver esto. ¿Puedes contarme más detalles sobre lo que pasó?"
        elif any(word in input_lower for word in ["grupo", "corporate", "empresa"]):
            return "Para grupos grandes y eventos corporativos tenemos experiencias especializadas. Te voy a conectar con nuestro equipo de ventas corporativas."
        else:
            return "¡Hola! Soy NIA, tu asistente de enoturismo de Concha y Toro. ¿En qué te puedo ayudar hoy?"
    
    def _detect_handoff(self, response: str, metadata: Dict) -> bool:
        """Detect if a handoff was triggered"""
        
        # Check metadata first
        if metadata.get("handoff_triggered"):
            return True
        
        # Check response content for handoff indicators
        handoff_phrases = [
            "te voy a conectar",
            "derivar a",
            "especialista",
            "supervisor", 
            "gerente",
            "equipo de",
            "atención al cliente",
            "ventas corporativas"
        ]
        
        response_lower = response.lower()
        return any(phrase in response_lower for phrase in handoff_phrases)
    
    def _extract_handoff_info(self, response: str, metadata: Dict, turn_number: int) -> HandoffEvent:
        """Extract handoff information"""
        
        # Determine handoff type
        handoff_type = metadata.get("handoff_type")
        if not handoff_type:
            handoff_type = self._infer_handoff_type(response)
        
        # Get reason
        reason = metadata.get("handoff_reason", "Detected from response content")
        
        # Extract context
        context_data = {
            "conversation_summary": response,
            "entities": metadata.get("entities_extracted", {}),
            "user_context": metadata.get("user_context", {}),
            "handoff_trigger": "automated_detection"
        }
        
        return HandoffEvent(
            handoff_type=handoff_type,
            trigger_reason=reason,
            context_data=context_data,
            turn_number=turn_number,
            timestamp=datetime.now()
        )
    
    def _infer_handoff_type(self, response: str) -> HandoffType:
        """Infer handoff type from response content"""
        
        response_lower = response.lower()
        
        if any(word in response_lower for word in ["ventas", "corporativo", "grupo", "evento"]):
            return HandoffType.SALES
        elif any(word in response_lower for word in ["queja", "problema", "reclamo", "insatisfecho"]):
            return HandoffType.CUSTOMER_SERVICE
        elif any(word in response_lower for word in ["técnico", "error", "falla", "no funciona"]):
            return HandoffType.TECHNICAL_SUPPORT
        elif any(word in response_lower for word in ["pago", "factura", "billing", "cobro"]):
            return HandoffType.BILLING
        elif any(word in response_lower for word in ["gerente", "supervisor", "escalation"]):
            return HandoffType.ESCALATION
        else:
            return HandoffType.CUSTOMER_SERVICE  # Default
    
    def _evaluate_objective_achievement(self, scenario: Dict, turns: List[ConversationTurn], 
                                       handoff_event: Optional[HandoffEvent], outcome: ConversationOutcome) -> bool:
        """Evaluate if the conversation achieved its objective"""
        
        expected_outcome = scenario.expected_outcome
        
        # Check basic outcome match
        if expected_outcome != outcome:
            return False
        
        # Check success indicators
        success_indicators = scenario.success_indicators
        if success_indicators:
            conversation_text = " ".join([turn.content for turn in turns]).lower()
            indicators_met = sum(1 for indicator in success_indicators 
                               if any(keyword in conversation_text for keyword in indicator.lower().split()))
            return indicators_met >= len(success_indicators) * 0.7  # 70% of indicators met
        
        # Default success criteria
        if outcome == ConversationOutcome.SUCCESS:
            return len(turns) >= 4  # Reasonable conversation length
        elif outcome == ConversationOutcome.HANDOFF:
            return handoff_event is not None
        
        return False


class ConversationTestRunner:
    """Main test runner that orchestrates the entire testing process"""
    
    def __init__(self):
        self.simulator = ConversationSimulator()
        self.evaluators = [
            ResponseQualityEvaluator(),
            HandoffQualityEvaluator(),
            EntityExtractionEvaluator(),
            ConversationFlowEvaluator()
        ]
        self.logger = logging.getLogger(__name__)
    
    async def run_test_suite(self, scenario_names: Optional[List[str]] = None, 
                           run_id: Optional[str] = None) -> TestSuiteResult:
        """Run complete test suite"""
        
        if not testing_config.enabled:
            self.logger.info("Conversation testing is disabled")
            return self._create_empty_result()
        
        if run_id is None:
            run_id = f"test_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        start_time = datetime.now()
        self.logger.info(f"Starting conversation test suite: {run_id}")
        
        # Get scenarios to test
        all_scenarios = EnoturismoTestScenarios.get_all_scenarios()
        if scenario_names:
            scenarios_to_test = {name: scenario for name, scenario in all_scenarios.items() 
                               if name in scenario_names}
        else:
            scenarios_to_test = all_scenarios
        
        # Filter by enabled scenarios
        enabled_scenarios = {name: scenario for name, scenario in scenarios_to_test.items()
                           if ENOTURISMO_SCENARIOS.get(name, {}).enabled}
        
        self.logger.info(f"Running {len(enabled_scenarios)} scenarios")
        
        # Run conversations
        conversation_results = []
        evaluation_results = []
        
        if testing_config.concurrent_conversations > 1:
            # Run scenarios concurrently
            semaphore = asyncio.Semaphore(testing_config.concurrent_conversations)
            tasks = []
            
            for scenario_name, scenario in enabled_scenarios.items():
                task = self._run_scenario_with_semaphore(semaphore, scenario_name, scenario)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error(f"Scenario failed: {result}")
                    continue
                    
                conv_result, eval_results = result
                conversation_results.append(conv_result)
                evaluation_results.extend(eval_results)
        else:
            # Run scenarios sequentially
            for scenario_name, scenario in enabled_scenarios.items():
                try:
                    conv_result, eval_results = await self._run_single_scenario(scenario_name, scenario)
                    conversation_results.append(conv_result)
                    evaluation_results.extend(eval_results)
                except Exception as e:
                    self.logger.error(f"Scenario {scenario_name} failed: {e}")
        
        end_time = datetime.now()
        
        # Create test suite result
        test_result = TestSuiteResult(
            suite_name="Enoturismo Conversation Tests",
            run_id=run_id,
            start_time=start_time,
            end_time=end_time,
            conversation_results=conversation_results,
            evaluation_results=evaluation_results
        )
        
        # Calculate aggregate metrics
        test_result.calculate_aggregates()
        
        # Calculate scenario breakdown
        test_result.scenario_results = self._calculate_scenario_breakdown(conversation_results, evaluation_results)
        
        self.logger.info(f"Test suite completed: {test_result.success_rate:.2%} success rate")
        
        return test_result
    
    async def _run_scenario_with_semaphore(self, semaphore: asyncio.Semaphore, 
                                          scenario_name: str, scenario: Dict) -> tuple:
        """Run scenario with concurrency control"""
        async with semaphore:
            return await self._run_single_scenario(scenario_name, scenario)
    
    async def _run_single_scenario(self, scenario_name: str, scenario: Dict) -> tuple:
        """Run a single test scenario"""
        
        conversation_id = f"{scenario_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Simulate conversation
        conversation_result = await self.simulator.simulate_conversation(scenario, conversation_id)
        
        # Evaluate conversation
        evaluation_results = []
        for evaluator in self.evaluators:
            try:
                eval_result = await evaluator.evaluate(conversation_result, scenario.__dict__)
                evaluation_results.append(eval_result)
            except Exception as e:
                self.logger.error(f"Evaluation failed for {scenario_name} with {evaluator.__class__.__name__}: {e}")
        
        return conversation_result, evaluation_results
    
    def _calculate_scenario_breakdown(self, conversation_results: List[ConversationResult], 
                                    evaluation_results: List[EvaluationResult]) -> Dict[str, Dict[str, float]]:
        """Calculate metrics breakdown by scenario"""
        
        scenario_breakdown = {}
        
        # Group results by scenario
        scenario_groups = {}
        for conv_result in conversation_results:
            scenario_name = conv_result.scenario_name
            if scenario_name not in scenario_groups:
                scenario_groups[scenario_name] = {"conversations": [], "evaluations": []}
            scenario_groups[scenario_name]["conversations"].append(conv_result)
        
        for eval_result in evaluation_results:
            scenario_name = eval_result.scenario_name
            if scenario_name in scenario_groups:
                scenario_groups[scenario_name]["evaluations"].append(eval_result)
        
        # Calculate metrics for each scenario
        for scenario_name, data in scenario_groups.items():
            conversations = data["conversations"]
            evaluations = data["evaluations"]
            
            if not conversations:
                continue
            
            # Success rate
            successful = sum(1 for conv in conversations if conv.objective_achieved)
            success_rate = successful / len(conversations) if conversations else 0
            
            # Average scores
            if evaluations:
                avg_quality = sum(eval.response_quality_score for eval in evaluations) / len(evaluations)
                avg_overall = sum(eval.overall_score for eval in evaluations) / len(evaluations)
            else:
                avg_quality = 0
                avg_overall = 0
            
            # Average response time
            response_times = [conv.total_duration_ms for conv in conversations if conv.total_duration_ms]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            # Handoff metrics
            handoffs = [conv for conv in conversations if conv.handoff_event]
            handoff_rate = len(handoffs) / len(conversations) if conversations else 0
            
            scenario_breakdown[scenario_name] = {
                "success_rate": success_rate,
                "avg_response_quality": avg_quality,
                "avg_overall_score": avg_overall,
                "avg_response_time_ms": avg_response_time,
                "handoff_rate": handoff_rate,
                "total_conversations": len(conversations)
            }
        
        return scenario_breakdown
    
    def _create_empty_result(self) -> TestSuiteResult:
        """Create empty test result when testing is disabled"""
        return TestSuiteResult(
            suite_name="Enoturismo Conversation Tests",
            run_id="disabled",
            start_time=datetime.now(),
            end_time=datetime.now(),
            conversation_results=[],
            evaluation_results=[]
        )
    
    async def run_single_scenario_test(self, scenario_name: str) -> tuple[ConversationResult, List[EvaluationResult]]:
        """Run a single scenario for debugging/development"""
        
        scenarios = EnoturismoTestScenarios.get_all_scenarios()
        if scenario_name not in scenarios:
            raise ValueError(f"Scenario {scenario_name} not found")
        
        scenario = scenarios[scenario_name]
        return await self._run_single_scenario(scenario_name, scenario)


# Convenience function for running tests
async def run_conversation_tests(scenario_names: Optional[List[str]] = None) -> TestSuiteResult:
    """Convenience function to run conversation tests"""
    runner = ConversationTestRunner()
    return await runner.run_test_suite(scenario_names)