"""
Configuration for Conversation Testing Framework
Configurable settings for automated testing and improvement cycles
"""
from dataclasses import dataclass
from typing import List, Dict, Optional
import os


@dataclass
class ConversationTestingConfig:
    """Configuration for conversation testing framework"""
    
    # Base settings
    enabled: bool = True
    base_url: str = "http://localhost:8080"
    tenant_id: str = "concha-y-toro"
    
    # Test execution settings
    test_timeout: int = 30  # seconds
    concurrent_conversations: int = 3
    retry_attempts: int = 2
    
    # Evaluation thresholds
    min_response_quality: float = 0.8
    min_handoff_precision: float = 0.85
    min_conversation_success_rate: float = 0.75
    
    # Auto-improvement settings
    auto_improvement_enabled: bool = True
    improvement_cycle_days: int = 7  # Run improvement cycle every 7 days
    auto_deploy_threshold: float = 0.05  # Deploy if 5%+ improvement
    ab_test_duration_hours: int = 48
    
    # Reporting settings
    generate_html_reports: bool = True
    send_email_reports: bool = False
    report_recipients: List[str] = None
    
    # LLM settings for evaluation
    evaluation_model: str = "gpt-4"
    evaluation_temperature: float = 0.1
    
    def __post_init__(self):
        if self.report_recipients is None:
            self.report_recipients = []


@dataclass
class ScenarioConfig:
    """Configuration for individual test scenarios"""
    name: str
    enabled: bool = True
    priority: str = "medium"  # low, medium, high, critical
    max_turns: int = 10
    timeout_per_turn: int = 5
    expected_completion_rate: float = 0.8


# Global configuration instance
testing_config = ConversationTestingConfig(
    enabled=os.getenv("CONVERSATION_TESTING_ENABLED", "true").lower() == "true",
    base_url=os.getenv("OPENCHAT_BASE_URL", "http://localhost:8080"),
    tenant_id=os.getenv("TEST_TENANT_ID", "concha-y-toro"),
    auto_improvement_enabled=os.getenv("AUTO_IMPROVEMENT_ENABLED", "true").lower() == "true",
    evaluation_model=os.getenv("EVALUATION_MODEL", "gpt-4"),
    min_response_quality=float(os.getenv("MIN_RESPONSE_QUALITY", "0.8")),
    min_handoff_precision=float(os.getenv("MIN_HANDOFF_PRECISION", "0.85")),
    generate_html_reports=os.getenv("GENERATE_HTML_REPORTS", "true").lower() == "true"
)


# Scenario priorities for enoturismo
ENOTURISMO_SCENARIOS = {
    "tour_booking": ScenarioConfig(
        name="tour_booking",
        priority="critical",
        expected_completion_rate=0.9
    ),
    "price_inquiry": ScenarioConfig(
        name="price_inquiry", 
        priority="high",
        expected_completion_rate=0.95
    ),
    "schedule_check": ScenarioConfig(
        name="schedule_check",
        priority="high", 
        expected_completion_rate=0.9
    ),
    "large_group_booking": ScenarioConfig(
        name="large_group_booking",
        priority="critical",
        expected_completion_rate=0.8  # Expected handoff
    ),
    "complaint_handling": ScenarioConfig(
        name="complaint_handling",
        priority="critical",
        expected_completion_rate=0.9  # Expected handoff
    ),
    "weather_cancellation": ScenarioConfig(
        name="weather_cancellation",
        priority="medium"
    ),
    "gift_experience": ScenarioConfig(
        name="gift_experience",
        priority="medium"
    ),
    "accessibility_inquiry": ScenarioConfig(
        name="accessibility_inquiry",
        priority="high"
    )
}