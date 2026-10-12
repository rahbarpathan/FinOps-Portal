import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from src.agent.memory import WorkingMemory
from src.agent.tools.browser import BrowserController
from src.agent.tools.files import read_file_tool, list_files_tool
from src.agent.tools.human import HumanApprovalManager
from src.agent.verifier import IndependentVerifier
from src.agent.llm.base import BaseLLMProvider

class AutonomousAgent:
    """
    Autonomous AI Task Worker.
    Executes tasks using runtime ReAct planning, Playwright browser control,
    failure recovery, human approval gates, and independent outcome verification.
    """
    def __init__(
        self,
        run_id: str,
        task: str,
        provider: str = "auto",
        event_queue: Optional[asyncio.Queue] = None,
        is_cli: bool = False,
        max_steps: int = 15
    ):
        self.run_id = run_id
        self.task = task
        self.provider_name = provider
        self.event_queue = event_queue
        self.is_cli = is_cli
        self.max_steps = max_steps

        self.memory = WorkingMemory()
        self.browser = BrowserController()
        self.human = HumanApprovalManager(run_id=run_id, event_queue=event_queue, is_cli=is_cli)
        self.verifier = IndependentVerifier()
        self.llm = self._resolve_provider(provider)

    def _resolve_provider(self, name: str) -> BaseLLMProvider:
        name = name.lower()
        if name == "gemini" and os.getenv("GEMINI_API_KEY"):
            from src.agent.llm.gemini import GeminiProvider
            return GeminiProvider()
        elif name == "openai" and os.getenv("OPENAI_API_KEY"):
            from src.agent.llm.openai import OpenAIProvider
            return OpenAIProvider()
        elif name == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
            from src.agent.llm.anthropic import AnthropicProvider
            return AnthropicProvider()
        elif name == "offline":
            from src.agent.llm.mock import AutonomousOfflineEngine
            return AutonomousOfflineEngine()
        else:
            # Auto-detect key priority or fallback
            if os.getenv("GEMINI_API_KEY"):
                from src.agent.llm.gemini import GeminiProvider
                return GeminiProvider()
            elif os.getenv("OPENAI_API_KEY"):
                from src.agent.llm.openai import OpenAIProvider
                return OpenAIProvider()
            elif os.getenv("ANTHROPIC_API_KEY"):
                from src.agent.llm.anthropic import AnthropicProvider
                return AnthropicProvider()
            else:
                from src.agent.llm.mock import AutonomousOfflineEngine
                return AutonomousOfflineEngine()

    async def _emit(self, event_type: str, data: Dict[str, Any]):
        """Helper to emit events to web stream and/or CLI logger."""
        event = {"type": event_type, "timestamp": datetime.now().strftime("%H:%M:%S"), **data}
        if self.event_queue:
            await self.event_queue.put(event)

    async def run(self) -> Dict[str, Any]:
        """Main autonomous execution loop."""
        step = 0
        final_summary = ""
        final_evidence = {}
        success = False

        try:
            while step < self.max_steps:
                step += 1

                # 1. Observe current environment state
                page_summary = await self.browser.get_page_summary()

                # 2. LLM decides NEXT runtime action
                thought, tool_name, tool_args = self.llm.decide_next_step(
                    task=self.task,
                    history=self.memory.get_history(),
                    working_memory=self.memory.get_all_facts(),
                    page_summary=page_summary
                )

                # Emit step thinking & chosen action
                await self._emit("step", {
                    "step_number": step,
                    "phase": "ACTION",
                    "text": thought,
                    "code": f"tool: {tool_name}({json.dumps(tool_args)})"
                })

                # 3. Execute chosen tool
                obs_data = {}
                is_recovery = False

                if tool_name == "browser_navigate":
                    url = tool_args.get("url", "")
                    obs_data = await self.browser.navigate(url)

                elif tool_name == "browser_click":
                    target = tool_args.get("target", "")
                    obs_data = await self.browser.click(target)
                    # Detect if click triggered error or failure
                    if not obs_data.get("success"):
                        is_recovery = True

                elif tool_name == "browser_fill":
                    selector = tool_args.get("selector", "")
                    val = tool_args.get("value", "")
                    obs_data = await self.browser.fill(selector, val)

                elif tool_name == "browser_get_page_content":
                    obs_data = await self.browser.get_page_summary()

                elif tool_name == "browser_take_screenshot":
                    fn = tool_args.get("filename", f"step_{step}.png")
                    obs_data = await self.browser.take_screenshot(fn)
                    final_evidence["screenshot_url"] = obs_data.get("url")

                elif tool_name == "read_file":
                    p = tool_args.get("path", "")
                    obs_data = read_file_tool(p)

                elif tool_name == "list_files":
                    d = tool_args.get("directory", "data/invoices")
                    obs_data = list_files_tool(d)

                elif tool_name == "record_fact":
                    k = tool_args.get("key", "")
                    v = tool_args.get("value", "")
                    self.memory.record_fact(k, v)
                    obs_data = {"success": True, "fact_recorded": {k: v}}
                    await self._emit("facts_update", {"facts": self.memory.get_all_facts()})

                elif tool_name == "ask_human_approval":
                    act = tool_args.get("action", "")
                    det = tool_args.get("details", {})
                    rsn = tool_args.get("reason", "")
                    await self._emit("step", {
                        "step_number": step,
                        "phase": "HUMAN",
                        "text": f"Gated Action Approval Required: {rsn}",
                        "code": json.dumps(det, indent=2)
                    })
                    approval_res = await self.human.request_approval(act, det, rsn)
                    obs_data = approval_res
                    if approval_res.get("approved"):
                        self.memory.record_fact("human_approval_granted", True)

                elif tool_name == "finish_task":
                    final_summary = tool_args.get("summary", "Task completed.")
                    final_evidence.update(tool_args.get("evidence", {}))
                    success = True
                    obs_data = {"success": True, "status": "Task finished"}
                    
                    # Emit final observation
                    await self._emit("step", {
                        "step_number": step,
                        "phase": "OBSERVATION",
                        "text": f"Task Goal Satisfied: {final_summary}",
                        "code": json.dumps(final_evidence, indent=2)
                    })
                    break

                else:
                    obs_data = {"success": False, "error": f"Unknown tool: '{tool_name}'"}
                    is_recovery = True

                # Check if page has error alerts
                curr_summary = await self.browser.get_page_summary()
                if curr_summary.get("alerts"):
                    obs_data["page_alerts"] = curr_summary.get("alerts")
                    is_recovery = True

                # Emit observation or recovery
                phase_label = "RECOVERY" if is_recovery else "OBSERVATION"
                obs_summary = json.dumps(obs_data, indent=2)
                await self._emit("step", {
                    "step_number": step,
                    "phase": phase_label,
                    "text": f"Result: {'Success' if obs_data.get('success', True) else 'Failure detected'}",
                    "code": obs_summary
                })

                # Record in memory history for agent reflection in next step
                self.memory.add_history(
                    step_number=step,
                    thought=thought,
                    action=f"{tool_name}({json.dumps(tool_args)})",
                    observation=obs_summary
                )

                # Small operational pacing
                await asyncio.sleep(0.4)

            # 4. Independent Verification Audit (Ground Truth)
            await self._emit("step", {
                "step_number": step + 1,
                "phase": "VERIFICATION",
                "text": "Running Independent Verifier against ground-truth database state...",
                "code": "Query: Isolated /api/ground-truth checks"
            })

            verification_report = self.verifier.verify_task_outcome(self.task, final_evidence)

            await self._emit("completed", {
                "success": success and verification_report.get("is_verified", False),
                "summary": final_summary or "Execution concluded.",
                "evidence": final_evidence,
                "verification": verification_report
            })

            return {
                "success": success,
                "steps": step,
                "summary": final_summary,
                "verification": verification_report
            }

        finally:
            await self.browser.close()
