from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional

# Standard tool definitions provided to all LLM providers
AGENT_TOOLS_SCHEMA = [
    {
        "name": "browser_navigate",
        "description": "Navigate the browser to a given URL (e.g. 'http://localhost:8000/inbox' or 'http://localhost:8000/bills/create').",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The target URL to load in the browser"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "browser_get_page_content",
        "description": "Inspect the currently open browser page to observe visible text, form inputs, buttons, tables, and alert messages.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "browser_click",
        "description": "Click a visible button, link, or element on the current page using its selector or visible text (e.g. 'Create Bill', '#submit-bill-btn', 'Submit Payment Voucher', or attachment link).",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Element selector, ID, or visible button/link text"}
            },
            "required": ["target"]
        }
    },
    {
        "name": "browser_fill",
        "description": "Fill a form input or textarea on the page with a specific text or numeric value.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "Input element ID or name, e.g. 'vendor', 'invoice_number', 'amount', 'due_date', 'notes'"},
                "value": {"type": "string", "description": "The exact value to type into the field"}
            },
            "required": ["selector", "value"]
        }
    },
    {
        "name": "browser_take_screenshot",
        "description": "Capture a screenshot of the current browser page as proof and evidence.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Screenshot filename, e.g. 'bill_submitted.png'"}
            },
            "required": ["filename"]
        }
    },
    {
        "name": "read_file",
        "description": "Read a file from disk, such as an attached invoice document in data/invoices/.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative or absolute path to the file"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "list_files",
        "description": "List files in a directory to discover invoice documents.",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory path, e.g. 'data/invoices'"}
            }
        }
    },
    {
        "name": "record_fact",
        "description": "Save an important discovered fact in working memory (e.g. 'latest_invoice_num', 'amount', 'due_date', 'vendor').",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Fact identifier/key"},
                "value": {"type": "string", "description": "Discovered business fact or value"}
            },
            "required": ["key", "value"]
        }
    },
    {
        "name": "ask_human_approval",
        "description": "Request explicit human authorization when an action involves high risk, exceeds policy thresholds (> $10,000), or is ambiguous.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Description of the gated action to be performed"},
                "details": {"type": "object", "description": "Key parameters of the transaction (amount, vendor, invoice)"},
                "reason": {"type": "string", "description": "Why human authorization is required by company policy"}
            },
            "required": ["action", "details", "reason"]
        }
    },
    {
        "name": "finish_task",
        "description": "Signal that the natural language task has been completely and successfully fulfilled.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Concise summary of actions taken and final state"},
                "evidence": {"type": "object", "description": "Key evidence (e.g. bill_id, invoice_number, amount, screenshot_url)"}
            },
            "required": ["summary", "evidence"]
        }
    }
]

class BaseLLMProvider(ABC):
    """Abstract interface for LLM providers with native function/tool calling."""
    @abstractmethod
    def decide_next_step(
        self,
        task: str,
        history: List[Dict[str, Any]],
        working_memory: Dict[str, Any],
        page_summary: Dict[str, Any]
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        Returns:
            thought: The reasoning/reflection string explaining why this action was chosen.
            tool_name: The name of the tool to execute.
            tool_args: Dictionary of arguments for the tool.
        """
        pass
