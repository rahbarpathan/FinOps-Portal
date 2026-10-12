"""
Structured scratchpad memory and bounded history windowing for the autonomous agent.
Maintains extracted facts with sources, injected into every step.
"""
from typing import Dict, Any, List, Optional

class ScratchpadMemory:
    """
    Structured scratchpad memory that tracks extracted facts and their sources.
    Injected into every step prompt, kept separate from the raw action history.
    """
    def __init__(self):
        # Maps key -> {"value": Any, "source": str, "timestamp": str}
        self._facts: Dict[str, Dict[str, Any]] = {}

    def remember(self, key: str, value: Any, source: str = "observation") -> Dict[str, Any]:
        """Store a fact with its provenance source."""
        self._facts[key] = {
            "value": value,
            "source": source
        }
        return {"success": True, "key": key, "value": value, "source": source}

    def recall(self, key: Optional[str] = None) -> Any:
        """Recall a specific fact or all facts."""
        if key is not None:
            entry = self._facts.get(key)
            return entry["value"] if entry else None
        return {k: v["value"] for k, v in self._facts.items()}

    def get_structured_facts(self) -> Dict[str, Dict[str, Any]]:
        """Return raw facts with metadata."""
        return dict(self._facts)

    def render_prompt_view(self) -> str:
        """Render formatted scratchpad for LLM context injection."""
        if not self._facts:
            return "No facts recorded in scratchpad memory yet."
        lines = ["STRUCTURED SCRATCHPAD (DISCOVERED FACTS & SOURCES):"]
        for k, v in self._facts.items():
            lines.append(f"  • {k}: {v['value']} (Source: {v['source']})")
        return "\n".join(lines)

    def clear(self):
        self._facts.clear()


class BoundedHistory:
    """
    Action history manager that bounds prompt context by truncating/summarizing older steps.
    """
    def __init__(self, max_recent_steps: int = 8):
        self.max_recent_steps = max_recent_steps
        self.steps: List[Dict[str, Any]] = []

    def add_step(self, step_number: int, thought: str, tool: str, args: Dict[str, Any], result: Any, error_class: Optional[str] = None):
        self.steps.append({
            "step": step_number,
            "thought": thought,
            "tool": tool,
            "args": args,
            "result": result,
            "error_class": error_class
        })

    def render_prompt_history(self) -> str:
        """Render recent steps in full detail, and summarize older steps."""
        if not self.steps:
            return "No previous steps executed."

        total = len(self.steps)
        if total <= self.max_recent_steps:
            recent = self.steps
            prefix = ""
        else:
            older_count = total - self.max_recent_steps
            recent = self.steps[-self.max_recent_steps:]
            prefix = f"[{older_count} earlier steps summarized: steps 1 through {older_count} executed previously]\n"

        lines = [prefix]
        for s in recent:
            err_tag = f" [ERROR: {s['error_class']}]" if s.get('error_class') else ""
            lines.append(
                f"Step {s['step']}{err_tag}:\n"
                f"  Thought: {s['thought']}\n"
                f"  Tool: {s['tool']}({s['args']})\n"
                f"  Result: {str(s['result'])[:300]}"
            )
        return "\n".join(lines)
