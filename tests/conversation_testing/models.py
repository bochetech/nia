"""
Data models for conversation testing framework
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum


class ConversationOutcome(Enum):
    """Possible outcomes of a conversation"""
    SUCCESS = "success"
    HANDOFF = "handoff" 
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"


class HandoffType(Enum):
    """Types of handoffs"""
    SALES = "sales"
    CUSTOMER_SERVICE = "customer_service"  
    TECHNICAL_SUPPORT = "technical_support"
    BILLING = "billing"
    ESCALATION = "escalation"


class MessageRole(Enum):
    """Message roles in conversation"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ConversationTurn:
    """Single turn in a conversation"""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Response analysis
    response_time_ms: Optional[int] = None
    token_count: Optional[int] = None
    
    # Evaluation scores (filled by evaluators)
    relevance_score: Optional[float] = None
    accuracy_score: Optional[float] = None
    tone_score: Optional[float] = None


@dataclass
class HandoffEvent:
    """Information about a handoff event"""
    handoff_type: HandoffType
    trigger_reason: str
    context_data: Dict[str, Any]
    turn_number: int
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Quality metrics
    was_appropriate: Optional[bool] = None
    context_preservation_score: Optional[float] = None
    timing_score: Optional[float] = None


@dataclass
class ConversationResult:
    """Complete result of a test conversation"""
    scenario_name: str
    conversation_id: str
    turns: List[ConversationTurn]
    outcome: ConversationOutcome
    handoff_event: Optional[HandoffEvent] = None
    
    # Timing
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_duration_ms: Optional[int] = None
    
    # Success metrics
    objective_achieved: bool = False
    user_satisfaction_score: Optional[float] = None
    
    # Entity extraction results
    entities_extracted: Dict[str, Any] = field(default_factory=dict)
    expected_entities: Dict[str, Any] = field(default_factory=dict)
    
    # Error information
    error_message: Optional[str] = None
    failed_at_turn: Optional[int] = None


@dataclass  
class ScenarioDefinition:
    """Definition of a test scenario"""
    name: str
    description: str
    category: str  # e.g., "booking", "inquiry", "complaint"
    priority: str
    
    # Conversation flow
    user_inputs: List[str]
    expected_assistant_behaviors: List[Dict[str, Any]]
    
    # Success criteria
    expected_outcome: ConversationOutcome
    expected_entities: Dict[str, Any] = field(default_factory=dict)
    success_indicators: List[str] = field(default_factory=list)
    
    # Handoff criteria (if expected)
    expected_handoff_type: Optional[HandoffType] = None
    handoff_trigger_keywords: List[str] = field(default_factory=list)
    
    # Quality thresholds
    min_relevance_score: float = 0.8
    min_accuracy_score: float = 0.8
    min_tone_score: float = 0.7
    
    # Metadata
    created_by: str = "system"
    created_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """Result of evaluating a conversation"""
    conversation_id: str
    scenario_name: str
    
    # Overall scores
    overall_score: float
    success: bool
    
    # Detailed scores
    response_quality_score: float
    handoff_quality_score: Optional[float] = None
    entity_extraction_score: float = 0.0
    conversation_flow_score: float = 0.0
    
    # Specific metrics
    relevance_scores: List[float] = field(default_factory=list)
    accuracy_scores: List[float] = field(default_factory=list) 
    tone_scores: List[float] = field(default_factory=list)
    
    # Analysis
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)
    
    # Performance metrics
    avg_response_time_ms: Optional[float] = None
    total_tokens_used: Optional[int] = None


@dataclass
class TestSuiteResult:
    """Results of running a complete test suite"""
    suite_name: str
    run_id: str
    start_time: datetime
    end_time: datetime
    
    # Conversation results
    conversation_results: List[ConversationResult]
    evaluation_results: List[EvaluationResult]
    
    # Aggregate metrics
    total_conversations: int = 0
    successful_conversations: int = 0
    success_rate: float = 0.0
    avg_conversation_length: float = 0.0
    avg_response_time_ms: float = 0.0
    
    # Handoff metrics
    total_handoffs: int = 0
    appropriate_handoffs: int = 0
    handoff_precision: float = 0.0
    
    # Quality metrics
    avg_response_quality: float = 0.0
    avg_entity_extraction_score: float = 0.0
    
    # By scenario breakdown
    scenario_results: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Trend data (if available)
    trend_comparison: Optional[Dict[str, float]] = None
    
    def calculate_aggregates(self):
        """Calculate aggregate metrics from individual results"""
        if not self.evaluation_results:
            return
            
        self.total_conversations = len(self.conversation_results)
        self.successful_conversations = sum(1 for r in self.conversation_results if r.objective_achieved)
        self.success_rate = self.successful_conversations / self.total_conversations if self.total_conversations > 0 else 0
        
        # Response time calculation
        response_times = [r.total_duration_ms for r in self.conversation_results if r.total_duration_ms]
        self.avg_response_time_ms = sum(response_times) / len(response_times) if response_times else 0
        
        # Conversation length
        conversation_lengths = [len(r.turns) for r in self.conversation_results]
        self.avg_conversation_length = sum(conversation_lengths) / len(conversation_lengths) if conversation_lengths else 0
        
        # Quality scores
        quality_scores = [r.response_quality_score for r in self.evaluation_results]
        self.avg_response_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        
        # Handoff metrics
        self.total_handoffs = sum(1 for r in self.conversation_results if r.handoff_event)
        handoff_quality_scores = [r.handoff_event.was_appropriate for r in self.conversation_results 
                                if r.handoff_event and r.handoff_event.was_appropriate is not None]
        self.appropriate_handoffs = sum(handoff_quality_scores)
        self.handoff_precision = self.appropriate_handoffs / self.total_handoffs if self.total_handoffs > 0 else 1.0