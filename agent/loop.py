"""
Core Autonomous ReAct Execution Loop.
Domain-agnostic execution engine orchestrating observations, thoughts, tool dispatch,
error classification, loop detection, safety policy gates, and verification.
"""
import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from agent.memory import ScratchpadMemory, BoundedHistory
from agent.reliability import (
    classify_tool_error, is_transient_error, LoopDetector, BudgetManager
)
from agent.policy import SafetyPolicy
from agent.tools import ToolManager
from agent.verifier import IndependentVerifier
from agent.logging import ExecutionLogger
from agent.llm import get_llm_engine, BaseLLM

class AgentLoop:
    """
    Autonomous AI Task Worker execution loop.
    Domain-agnostic and works unchanged across all tasks.
    """
    def __init__(
        self,
        task: str,
        run_id: Optional[str] = None,
        provider: str = "auto",
        max_steps: int = 30,
        max_seconds: float = 180.0,
        event_queue: Optional[asyncio.Queue] = None,
        is_cli: bool = False,
        auto_approve: Optional[bool] = None
    ):
        self.task = task
        self.run_id = run_id or f"run_{datetime.now().strftime('%H%M%S')}"
        self.provider = provider
        self.max_steps = max_steps
        self.event_queue = event_queue
        self.is_cli = is_cli

        self.memory = ScratchpadMemory()
        self.history = BoundedHistory()
        self.budget = BudgetManager(max_steps=max_steps, max_seconds=max_seconds)
        self.loop_detector = LoopDetector(repeat_threshold=3)
        self.policy = SafetyPolicy(auto_approve=auto_approve)
        self.tools = ToolManager(run_id=self.run_id)
        self.verifier = IndependentVerifier()
        self.logger = ExecutionLogger(run_id=self.run_id, task=self.task)
        self.llm = get_llm_engine(provider)

        self.retries_count = 0
        self.approvals_count = 0
        self.last_error_class: Optional[str] = None
        self.final_evidence: Dict[str, Any] = {}

    async def _emit(self, event_type: str, data: Dict[str, Any]):
        event = {"type": event_type, "timestamp": datetime.now().strftime("%H:%M:%S"), **data}
        if self.event_queue:
            await self.event_queue.put(event)

    async def run(self) -> Dict[str, Any]:
        """Main ReAct execution loop."""
        step = 0
        success = False
        final_status = "unverified"
        final_summary = ""
        verification_report = None

        try:
            while True:
                # 1. Budget check
                is_exceeded, budget_reason = self.budget.record_step()
                if is_exceeded:
                    final_summary = f"Execution stopped: {budget_reason}"
                    break
                step = self.budget.current_step

                # 2. Observe: Capture accessibility tree snapshot
                snapshot = await self.tools.browser_snapshot()
                tree = snapshot.get("accessibility_tree", "")
                title = snapshot.get("title", "")

                # Detect page-level errors rendered in the browser DOM
                alert_lines = [line for line in tree.split("\n") if line.strip().startswith("[ALERT]")]
                alert_text = " ".join(alert_lines).lower()

                if "500" in title or "internal server error" in alert_text or "database lock" in alert_text or "500" in alert_text:
                    self.last_error_class = "http_5xx"
                    self.retries_count += 1
                elif alert_lines and ("validation" in alert_text or "invalid" in alert_text or "error" in alert_text):
                    self.last_error_class = "validation_error"
                else:
                    self.last_error_class = None

                # 3. Think & Plan next action
                scratchpad_view = self.memory.render_prompt_view()
                history_view = self.history.render_prompt_history()

                thought, tool_name, tool_args = self.llm.plan_next_action(
                    task=self.task,
                    scratchpad_str=scratchpad_view,
                    history_str=history_view,
                    current_snapshot=snapshot,
                    last_error_class=self.last_error_class
                )

                # 4. Loop Detection Check
                is_loop, should_escalate, loop_msg = self.loop_detector.record_action(tool_name, tool_args)
                if should_escalate:
                    tool_name = "ask_user"
                    tool_args = {"question": loop_msg, "kind": "clarification"}
                elif is_loop:
                    thought = f"RE-PLANNING: {loop_msg}. " + thought

                # Emit Step Event
                await self._emit("step", {
                    "step_number": step,
                    "phase": "ACTION",
                    "text": thought,
                    "code": f"tool: {tool_name}({json.dumps(tool_args)})"
                })

                # 5. Safety & Human-in-the-Loop Policy Gate
                is_side_effect, side_effect_reason = self.policy.is_side_effecting_action(tool_name, tool_args)
                if is_side_effect and tool_name != "ask_user":
                    if not self.policy.auto_approve:
                        # Gated action requires approval
                        self.approvals_count += 1
                        await self._emit("step", {
                            "step_number": step,
                            "phase": "HUMAN",
                            "text": f"Gated Action Approval Required: {side_effect_reason}",
                            "code": json.dumps(tool_args, indent=2)
                        })

                        # In CLI mode, prompt user if terminal attached
                        approved = False
                        if self.is_cli:
                            try:
                                ans = input(f"\n[!] Authorize action '{tool_name}' ({side_effect_reason})? [y/N]: ").strip().lower()
                                approved = ans in ("y", "yes")
                            except Exception:
                                approved = False
                        elif self.event_queue:
                            from env.app import active_runs
                            loop = asyncio.get_running_loop()
                            fut = loop.create_future()
                            if self.run_id in active_runs:
                                active_runs[self.run_id]["approval_future"] = fut
                            await self._emit("approval_request", {"request": {"tool": tool_name, "args": tool_args, "reason": side_effect_reason}})
                            try:
                                approved = await asyncio.wait_for(fut, timeout=60.0)
                            except asyncio.TimeoutError:
                                approved = False

                        if not approved:
                            result = {"success": False, "error": "Action rejected by human operator"}
                            self.last_error_class = "action_rejected"
                            self.history.add_step(step, thought, tool_name, tool_args, result, self.last_error_class)
                            self.logger.log_step(step, thought, tool_name, tool_args, result, self.last_error_class)
                            continue
                    else:
                        self.approvals_count += 1

                # 6. Execute Tool
                result = {}
                error_class = None

                if tool_name == "browser_goto":
                    result = await self.tools.browser_goto(tool_args.get("url", ""))

                elif tool_name == "browser_snapshot":
                    result = await self.tools.browser_snapshot()

                elif tool_name == "browser_click":
                    result = await self.tools.browser_click(tool_args.get("ref", ""))

                elif tool_name == "browser_type":
                    result = await self.tools.browser_type(tool_args.get("ref", ""), tool_args.get("text", ""))

                elif tool_name == "browser_select":
                    result = await self.tools.browser_select(tool_args.get("ref", ""), tool_args.get("option", ""))

                elif tool_name == "browser_extract_text":
                    result = await self.tools.browser_extract_text(tool_args.get("ref", ""))

                elif tool_name == "browser_screenshot":
                    result = await self.tools.browser_screenshot(tool_args.get("filename"))
                    if result.get("url"):
                        self.final_evidence["screenshot_url"] = result["url"]

                elif tool_name == "read_file":
                    result = self.tools.read_file(tool_args.get("path", ""))

                elif tool_name == "write_file":
                    result = self.tools.write_file(tool_args.get("path", ""), tool_args.get("content", ""))

                elif tool_name == "list_files":
                    result = self.tools.list_files(tool_args.get("dir", "."))

                elif tool_name == "http_request":
                    result = await self.tools.http_request(tool_args.get("method", "GET"), tool_args.get("url", ""), tool_args.get("body"))

                elif tool_name == "remember":
                    k = tool_args.get("key", "")
                    v = tool_args.get("value", "")
                    src = tool_args.get("source", "observation")
                    result = self.memory.remember(k, v, src)
                    await self._emit("facts_update", {"facts": self.memory.recall()})

                elif tool_name == "recall":
                    result = {"success": True, "facts": self.memory.recall(tool_args.get("key"))}

                elif tool_name == "ask_user":
                    q = tool_args.get("question", "")
                    kind = tool_args.get("kind", "clarification")
                    self.final_evidence["clarification_asked"] = True
                    self.final_evidence["question"] = q
                    self.final_evidence["question_kind"] = kind
                    await self._emit("step", {
                        "step_number": step,
                        "phase": "HUMAN",
                        "text": f"User Prompt [{kind.upper()}]: {q}",
                        "code": json.dumps(tool_args, indent=2)
                    })
                    result = {"success": True, "status": "paused_waiting_for_user", "question": q}
                    if kind == "clarification":
                        final_status = "verified"
                        final_summary = f"Clarification required: {q}"
                        success = True
                        break

                elif tool_name == "verify":
                    crit = tool_args.get("criterion", "")
                    exp = tool_args.get("expected")
                    act = tool_args.get("actual")
                    check_type = tool_args.get("check_type", "ground_truth")
                    result = self.verifier.add_check(crit, exp, act, check_type)

                elif tool_name == "finish":
                    # Critical rule: 'finish' is rejected unless a verification result is attached!
                    requested_status = tool_args.get("status", "unverified")
                    summary = tool_args.get("summary", "")

                    # Run independent verification
                    verification_report = self.verifier.verify_outcome(self.task, self.final_evidence)

                    if not verification_report.get("is_verified", False) and requested_status == "verified":
                        # Reject claim of success without evidence
                        result = {
                            "success": False,
                            "error": "Finish rejected: Claimed 'verified' status but independent ground-truth verification checks failed.",
                            "verification_report": verification_report
                        }
                        error_class = "verification_rejected"
                    else:
                        final_status = verification_report.get("status", requested_status)
                        final_summary = summary
                        success = verification_report.get("is_verified", False)
                        result = {"success": True, "final_status": final_status, "verification": verification_report}
                        break

                else:
                    result = {"success": False, "error": f"Unknown tool '{tool_name}'"}
                    error_class = "unknown_tool"

                # 7. Classify Tool Errors & Transient Retries
                if not result.get("success", True) and not error_class:
                    error_class = classify_tool_error(result.get("error", ""), result.get("status_code"))
                    if is_transient_error(error_class):
                        self.retries_count += 1
                        await asyncio.sleep(0.5)

                self.last_error_class = error_class

                # 8. Record in History & Trace Logger
                self.history.add_step(step, thought, tool_name, tool_args, result, error_class)
                self.logger.log_step(step, thought, tool_name, tool_args, result, error_class, self.memory.get_structured_facts())

                # Emit Observation
                phase_label = "RECOVERY" if error_class else "OBSERVATION"
                await self._emit("step", {
                    "step_number": step,
                    "phase": phase_label,
                    "text": f"Observation: {'Success' if result.get('success', True) else f'Error ({error_class})'}",
                    "code": json.dumps(result, indent=2)
                })

                await asyncio.sleep(0.3)

            # 9. Post-execution Final Verification
            if not verification_report:
                verification_report = self.verifier.verify_outcome(self.task, self.final_evidence)
                success = verification_report.get("is_verified", False)
                final_status = verification_report.get("status", "failed")

            # Finalize run trace
            self.logger.finalize(success, final_status, final_summary, verification_report)

            # Emit completion event
            await self._emit("completed", {
                "success": success,
                "status": final_status,
                "summary": final_summary,
                "steps": step,
                "retries": self.retries_count,
                "approvals": self.approvals_count,
                "time_seconds": round(self.budget.elapsed_seconds, 2),
                "verification": verification_report
            })

            return {
                "success": success,
                "status": final_status,
                "summary": final_summary,
                "steps": step,
                "retries": self.retries_count,
                "approvals": self.approvals_count,
                "time_seconds": round(self.budget.elapsed_seconds, 2),
                "verification": verification_report
            }

        finally:
            await self.tools.close()
