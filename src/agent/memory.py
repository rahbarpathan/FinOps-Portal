from typing import Dict, Any, Optional

class WorkingMemory:
    """
    Persistent working memory for the autonomous agent.
    Remembers key business facts discovered during execution.
    """
    def __init__(self):
        self._facts: Dict[str, Any] = {}
        self._action_history: list = []

    def record_fact(self, key: str, value: Any):
        self._facts[key] = value

    def get_fact(self, key: str, default: Any = None) -> Any:
        return self._facts.get(key, default)

    def get_all_facts(self) -> Dict[str, Any]:
        return dict(self._facts)

    def add_history(self, step_number: int, thought: str, action: str, observation: str):
        self._action_history.append({
            "step": step_number,
            "thought": thought,
            "action": action,
            "observation": observation
        })

    def get_history(self) -> list:
        return list(self._action_history)

    def clear(self):
        self._facts.clear()
        self._action_history.clear()
