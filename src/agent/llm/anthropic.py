import os
import json
from typing import Dict, Any, List, Tuple
from src.agent.llm.base import BaseLLMProvider, AGENT_TOOLS_SCHEMA

class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str = None, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set.")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    def decide_next_step(
        self,
        task: str,
        history: List[Dict[str, Any]],
        working_memory: Dict[str, Any],
        page_summary: Dict[str, Any]
    ) -> Tuple[str, str, Dict[str, Any]]:
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)

        system_instruction = (
            "You are an Autonomous AI Task Worker in an enterprise FinOps environment. "
            "Your job is to accomplish the user's business goal using available browser, file, and approval tools. "
            "Rules:\n"
            "1. You MUST decide each next action dynamically based on page observation, history, and memory.\n"
            "2. When comparing invoices from a vendor, compare the issue/received dates carefully to select the LATEST invoice.\n"
            "3. Internal Finance System strictly requires due date formatted as YYYY-MM-DD and amount as numeric without currency symbols.\n"
            "4. If an invoice total exceeds $10,000, company policy requires you to invoke 'ask_human_approval' before submitting.\n"
            "5. If a submission fails (e.g. 500 server error, validation error, or changed button layout), observe the error and retry or adapt.\n"
            "6. Call 'finish_task' once the bill has been recorded and verified.\n"
            "Always include your step-by-step reasoning."
        )

        user_content = f"""
MISSION OBJECTIVE: {task}

CURRENT WORKING MEMORY (FACTS DISCOVERED SO FAR):
{json.dumps(working_memory, indent=2)}

CURRENT BROWSER STATE:
- URL: {page_summary.get('url')}
- Title: {page_summary.get('title')}
- Visible Alerts/Errors: {json.dumps(page_summary.get('alerts', []))}
- Visible Form Inputs: {json.dumps(page_summary.get('form_inputs', []))}
- Visible Buttons: {json.dumps(page_summary.get('interactive_buttons', []))}
- Table Data: {json.dumps(page_summary.get('table_data', []))}
- Content Excerpt:
{page_summary.get('text_preview', '')[:800]}

ACTION HISTORY (LAST {len(history)} STEPS):
{json.dumps(history[-6:], indent=2) if history else "No actions taken yet."}

Decide your next action and tool call.
"""

        # Format tools for Claude
        claude_tools = []
        for t in AGENT_TOOLS_SCHEMA:
            claude_tools.append({
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"]
            })

        response = client.messages.create(
            model=self.model,
            system=system_instruction,
            messages=[{"role": "user", "content": user_content}],
            tools=claude_tools,
            max_tokens=1024,
            temperature=0.1
        )

        thought = ""
        tool_name = "browser_get_page_content"
        tool_args = {}

        for block in response.content:
            if block.type == "text":
                thought += block.text
            elif block.type == "tool_use":
                tool_name = block.name
                tool_args = block.input or {}

        if not thought:
            thought = f"Invoking tool {tool_name} based on current page state."

        return thought, tool_name, tool_args
