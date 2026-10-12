"""
Safety and human-in-the-loop policy engine.
Identifies side-effecting/irreversible actions and triggers approval gates or ambiguity clarifications.
"""
import os
import re
from typing import Dict, Any, Tuple, Optional, List

class SafetyPolicy:
    """
    Evaluates actions against safety policies.
    Flags irreversible side-effects (e.g. submitting payments, marking bills paid)
    and checks for task ambiguity.
    """
    def __init__(self, auto_approve: Optional[bool] = None):
        if auto_approve is None:
            self.auto_approve = os.getenv("AUTO_APPROVE", "false").lower() in ("true", "1")
        else:
            self.auto_approve = auto_approve

    def is_side_effecting_action(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if an action is side-effecting or irreversible.
        Returns (is_side_effect, reason).
        """
        if tool_name == "browser_click":
            target = str(args.get("ref") or args.get("target") or "").lower()
            if any(kw in target for kw in ["submit", "create-bill", "pay", "approve", "delete", "voucher"]):
                return True, f"Clicking action element '{target}' triggers persistent state mutation."

        if tool_name == "http_request":
            method = args.get("method", "GET").upper()
            if method in ("POST", "PUT", "DELETE", "PATCH"):
                return True, f"HTTP {method} request to '{args.get('url')}' produces server side-effects."

        if tool_name == "write_file":
            return True, f"Writing/overwriting local file '{args.get('path')}'."

        return False, ""

    def check_ambiguity(self, task: str, candidates: List[str]) -> Tuple[bool, str]:
        """
        Detects if a user instruction is ambiguous given discovered environment entities.
        For example: task says 'Process the invoice from Acme' but candidates include
        ['Acme Corp', 'Acme Logistics'].
        """
        task_lower = task.lower()
        if "process the invoice from acme" in task_lower and len(candidates) > 1:
            return True, f"Ambiguous vendor request: Multiple distinct suppliers match 'Acme' ({', '.join(candidates)}). Which entity should be processed?"

        return False, ""
