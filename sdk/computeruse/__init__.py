"""
ComputerUse SDK - One API to automate any web workflow

Example:
    from computeruse import ComputerUse

    cu = ComputerUse()
    result = cu.run_task(
        url="https://example.com",
        task="Extract the page title",
        output_schema={"title": "str"}
    )

    print(result.result["title"])
"""

from computeruse.client import ComputerUse
from computeruse.exceptions import (
    APIError,
    AuthenticationError,
    BrowserError,
    ComputerUseError,
    ComputerUseSDKError,
    NetworkError,
    RateLimitError,
    RetryExhaustedError,
    ServiceUnavailableError,
    SessionError,
    TaskExecutionError,
    TaskTimeoutError,
    TimeoutError,
    ValidationError,
)
from computeruse.models import ActionType, StepData, TaskConfig, TaskResult

from computeruse.cost import COST_PER_M_INPUT, COST_PER_M_OUTPUT, calculate_cost_cents, calculate_cost_from_steps
from computeruse.error_classifier import ClassifiedError, ErrorCategory, classify_error, classify_error_message
from computeruse.replay_generator import ReplayGenerator
from computeruse.retry_policy import MAX_DELAY_SECONDS, RETRIABLE_CATEGORIES, RetryDecision, should_retry_task
from computeruse.stuck_detector import StuckDetector, StuckSignal
from computeruse.track import TrackConfig, TrackedPage, track
from computeruse.tracker import ObserviusTracker, TrackerConfig, create_tracker
from computeruse.wrap import WrappedAgent, WrapConfig, wrap
from computeruse.stagehand import StagehandConfig, TrackedStagehand, observe_stagehand
from computeruse.alerts import AlertConfig, AlertEmitter
from computeruse.analyzer import AnalysisConfig, AnalysisFinding, HistoryAnalyzer, LLMAnalyzer, RuleAnalyzer, RunAnalysis, RunAnalyzer
from computeruse.desktop import mss_screenshot_fn, pillow_screenshot_fn, pyautogui_screenshot_fn

__version__ = "0.1.0"

__all__ = [
    # Client
    "ComputerUse",
    # Models
    "TaskConfig",
    "TaskResult",
    # Exceptions (primary names)
    "ComputerUseSDKError",
    "TaskExecutionError",
    "BrowserError",
    "ValidationError",
    "AuthenticationError",
    "TaskTimeoutError",
    "RateLimitError",
    "NetworkError",
    "ServiceUnavailableError",
    "RetryExhaustedError",
    "SessionError",
    "APIError",
    # Backward-compatible aliases
    "ComputerUseError",
    "TimeoutError",
    # Reliability features
    "ActionType",
    "StepData",
    "ErrorCategory",
    "ClassifiedError",
    "classify_error",
    "classify_error_message",
    "RetryDecision",
    "should_retry_task",
    "RETRIABLE_CATEGORIES",
    "MAX_DELAY_SECONDS",
    "StuckDetector",
    "StuckSignal",
    "ReplayGenerator",
    "calculate_cost_cents",
    "calculate_cost_from_steps",
    "COST_PER_M_INPUT",
    "COST_PER_M_OUTPUT",
    # Tracking
    "track",
    "TrackedPage",
    "TrackConfig",
    # Generic tracker
    "ObserviusTracker",
    "TrackerConfig",
    "create_tracker",
    # Wrapper
    "wrap",
    "WrappedAgent",
    "WrapConfig",
    # Stagehand
    "observe_stagehand",
    "TrackedStagehand",
    "StagehandConfig",
    # Alerts
    "AlertConfig",
    "AlertEmitter",
    # Analysis
    "AnalysisFinding",
    "RunAnalysis",
    "AnalysisConfig",
    "RuleAnalyzer",
    "HistoryAnalyzer",
    "LLMAnalyzer",
    "RunAnalyzer",
    # Desktop helpers
    "pyautogui_screenshot_fn",
    "pillow_screenshot_fn",
    "mss_screenshot_fn",
    # Metadata
    "__version__",
]
