"""
Reliability and error resilience for the autonomous agent.
Handles error classification, transient vs deterministic retries, loop detection,
and budget enforcement.
"""
import json
import time
from typing import Optional, Dict, Any, List, Tuple

# Standard error classifications
ERROR_ELEMENT_NOT_FOUND = "element_not_found"
ERROR_TIMEOUT = "timeout"
ERROR_VALIDATION = "validation_error"
ERROR_HTTP_5XX = "http_5xx"
ERROR_UNEXPECTED_PAGE = "unexpected_page"
ERROR_UNKNOWN = "unknown_error"

TRANSIENT_ERRORS = {ERROR_TIMEOUT, ERROR_HTTP_5XX}
DETERMINISTIC_ERRORS = {ERROR_ELEMENT_NOT_FOUND, ERROR_VALIDATION, ERROR_UNEXPECTED_PAGE}

import re

def classify_tool_error(error_msg: str, status_code: Optional[int] = None, page_alerts: Optional[List[str]] = None) -> str:
    """
    Classify an execution error into a standard semantic category.
    """
    msg = (error_msg or "").lower()
    alerts = [a.lower() for a in (page_alerts or [])]
    combined = msg + " " + " ".join(alerts)

    if status_code and 500 <= status_code < 600:
        return ERROR_HTTP_5XX
    if re.search(r"\b5\d{2}\b", combined) or "internal server error" in combined or "database lock" in combined:
        return ERROR_HTTP_5XX
    if "timeout" in combined or "timed out" in combined:
        return ERROR_TIMEOUT
    if "validation" in combined or "invalid" in combined or "strictly requires" in combined or "duplicate" in combined:
        return ERROR_VALIDATION
    if "404" in combined or "unexpected page" in combined:
        return ERROR_UNEXPECTED_PAGE
    if "not found" in combined or "waiting for selector" in combined or "no element matching" in combined:
        return ERROR_ELEMENT_NOT_FOUND

    return ERROR_UNKNOWN

def is_transient_error(error_class: str) -> bool:
    """Determine whether an error is transient (safe to retry) vs deterministic (requires strategy change)."""
    return error_class in TRANSIENT_ERRORS


class LoopDetector:
    """
    Detects repeated or circular action patterns.
    If the same action repeats or fails 3 times, triggers a forced re-plan.
    If it continues, flags escalation to ask_user.
    """
    def __init__(self, repeat_threshold: int = 3):
        self.repeat_threshold = repeat_threshold
        # Stores list of action signatures: (tool_name, serialized_args)
        self.action_history: List[str] = []
        self.consecutive_repeats = 0
        self.forced_replan_triggered = False

    def record_action(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, bool, str]:
        """
        Record action and evaluate loop state.
        Returns:
            (is_loop, should_escalate, guidance_message)
        """
        sig = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        if self.action_history and self.action_history[-1] == sig:
            self.consecutive_repeats += 1
        else:
            self.consecutive_repeats = 1
        self.action_history.append(sig)

        if self.consecutive_repeats >= self.repeat_threshold + 1:
            # Escalation to user
            return (
                True,
                True,
                f"LOOP DETECTED: Action '{tool_name}' has repeated {self.consecutive_repeats} times without progress. Escalating to user for guidance."
            )
        elif self.consecutive_repeats == self.repeat_threshold:
            self.forced_replan_triggered = True
            return (
                True,
                False,
                f"LOOP DETECTED: Action '{tool_name}' has been executed {self.repeat_threshold} times consecutively. You MUST change your strategy or tool approach immediately."
            )

        return (False, False, "")


class BudgetManager:
    """
    Enforces hard step budgets and time budgets.
    """
    def __init__(self, max_steps: int = 30, max_seconds: float = 180.0):
        self.max_steps = max_steps
        self.max_seconds = max_seconds
        self.start_time = time.time()
        self.current_step = 0

    def record_step(self) -> Tuple[bool, str]:
        """
        Increment step and check if budget exceeded.
        Returns:
            (is_exceeded, reason)
        """
        self.current_step += 1
        elapsed = time.time() - self.start_time

        if self.current_step > self.max_steps:
            return True, f"Step budget exceeded: reached {self.current_step} of {self.max_steps} max steps."
        if elapsed > self.max_seconds:
            return True, f"Time budget exceeded: elapsed {elapsed:.1f}s of {self.max_seconds:.1f}s max."

        return False, ""

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time
