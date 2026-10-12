"""
Execution trace logging for the autonomous agent.
Writes machine-readable JSONL run logs and human-readable Markdown traces to /runs.
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional

RUNS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runs")

class ExecutionLogger:
    """
    Records complete step-by-step traces for compliance, auditing, and debugging.
    """
    def __init__(self, run_id: str, task: str):
        self.run_id = run_id
        self.task = task
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(RUNS_DIR, exist_ok=True)

        self.jsonl_path = os.path.join(RUNS_DIR, f"run_{self.timestamp}_{self.run_id}.jsonl")
        self.trace_md_path = os.path.join(RUNS_DIR, f"trace_{self.timestamp}_{self.run_id}.md")

        # Initialize markdown trace header
        with open(self.trace_md_path, "w", encoding="utf-8") as f:
            f.write(f"# Autonomous Agent Run Trace — `{self.run_id}`\n\n")
            f.write(f"- **Objective:** {self.task}\n")
            f.write(f"- **Timestamp:** {self.timestamp}\n")
            f.write(f"- **Status:** Execution in progress\n\n---\n\n")

    def log_step(
        self,
        step: int,
        thought: str,
        tool: str,
        args: Dict[str, Any],
        result: Any,
        error_class: Optional[str] = None,
        scratchpad_snapshot: Optional[Dict[str, Any]] = None
    ):
        """Append step data to JSONL and Markdown trace."""
        step_record = {
            "step": step,
            "timestamp": datetime.now().isoformat(),
            "thought": thought,
            "tool": tool,
            "args": args,
            "result": result,
            "error_class": error_class,
            "scratchpad": scratchpad_snapshot or {}
        }

        # JSONL append
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(step_record) + "\n")

        # Markdown append
        with open(self.trace_md_path, "a", encoding="utf-8") as f:
            f.write(f"### Step {step} — `{tool}`\n\n")
            f.write(f"**Thought:** {thought}\n\n")
            f.write(f"```json\n// Arguments\n{json.dumps(args, indent=2)}\n```\n\n")
            if error_class:
                f.write(f"> ⚠️ **Error Classified:** `{error_class}`\n\n")
            res_str = json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
            f.write(f"**Observation / Result:**\n```json\n{res_str[:1200]}\n```\n\n---\n\n")

    def finalize(self, success: bool, status: str, summary: str, verification: Optional[Dict[str, Any]] = None):
        """Finalize the markdown trace with outcome and verification details."""
        with open(self.trace_md_path, "a", encoding="utf-8") as f:
            f.write(f"## Final Run Outcome: `{status.upper()}`\n\n")
            f.write(f"- **Summary:** {summary}\n")
            f.write(f"- **Verified:** {'Yes ✓' if success else 'No ✕'}\n\n")
            if verification:
                f.write("### Independent Verification Checks:\n\n")
                f.write("| Criterion | Result | Expected | Actual |\n|---|---|---|---|\n")
                for c in verification.get("checks", []):
                    res = "PASSED" if c.get("passed") else "FAILED"
                    f.write(f"| {c.get('criterion')} | **{res}** | `{c.get('expected')}` | `{c.get('actual')}` |\n")
                f.write(f"\n**Audit Proof Hash:** `{verification.get('audit_hash', 'N/A')}`\n")
