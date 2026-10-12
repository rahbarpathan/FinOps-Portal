import asyncio
import sys
from typing import Dict, Any, Optional

class HumanApprovalManager:
    """
    Manages policy checks and human-in-the-loop approvals.
    Supports both Web UI (via event queue & async future) and CLI (via terminal prompt).
    """
    def __init__(self, run_id: Optional[str] = None, event_queue: Optional[asyncio.Queue] = None, is_cli: bool = False):
        self.run_id = run_id
        self.event_queue = event_queue
        self.is_cli = is_cli

    async def request_approval(self, action: str, details: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """
        Prompts human for approval when action is sensitive or exceeds threshold.
        """
        request_data = {
            "action": action,
            "details": details,
            "reason": reason,
            "run_id": self.run_id
        }

        # CLI mode
        if self.is_cli:
            print("\n" + "="*60)
            print("[!] HUMAN APPROVAL REQUIRED")
            print(f"Action: {action}")
            print(f"Reason: {reason}")
            print("Details:")
            for k, v in details.items():
                print(f"  * {k}: {v}")
            print("="*60)
            
            try:
                if not sys.stdin.isatty() and os.getenv("AUTO_APPROVE", "false").lower() in ("true", "1"):
                    print("[Auto-Approve Flag Active] Authorizing action for non-interactive test run.")
                    approved = True
                else:
                    # Terminal prompt
                    answer = input("Authorize this agent action? [y/N]: ").strip().lower()
                    approved = answer in ("y", "yes")
            except Exception:
                approved = False

            return {
                "approved": approved,
                "responder": "cli_user",
                "notes": "Approved by operator" if approved else "Rejected by operator"
            }

        # Web UI mode
        if self.event_queue and self.run_id:
            from src.portal.app import active_runs
            loop = asyncio.get_running_loop()
            approval_fut = loop.create_future()
            
            if self.run_id in active_runs:
                active_runs[self.run_id]["approval_future"] = approval_fut

            # Emit approval_request event to SSE
            await self.event_queue.put({
                "type": "approval_request",
                "request": request_data
            })

            try:
                # Wait up to 120 seconds for user click in web UI
                approved = await asyncio.wait_for(approval_fut, timeout=120.0)
            except asyncio.TimeoutError:
                approved = False
                reason = "Approval timed out after 120 seconds"

            return {
                "approved": approved,
                "responder": "web_ui_user",
                "notes": "Approved in Web UI" if approved else "Rejected or timed out in Web UI"
            }

        # Fallback if unattached
        return {
            "approved": True,
            "responder": "auto_fallback",
            "notes": "Auto-approved (no UI channel attached)"
        }
