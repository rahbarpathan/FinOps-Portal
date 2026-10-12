import os
import json
from typing import Dict, Any, List, Tuple
from src.agent.llm.base import BaseLLMProvider, AGENT_TOOLS_SCHEMA

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")

    def decide_next_step(
        self,
        task: str,
        history: List[Dict[str, Any]],
        working_memory: Dict[str, Any],
        page_summary: Dict[str, Any]
    ) -> Tuple[str, str, Dict[str, Any]]:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)

        system_message = (
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

        tools = [{"type": "function", "function": t} for t in AGENT_TOOLS_SCHEMA]

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_content}
            ],
            tools=tools,
            tool_choice="auto",
            temperature=0.1
        )

        msg = response.choices[0].message
        thought = msg.content or "Analyzing next step based on observation."

        if msg.tool_calls:
            tool_call = msg.tool_calls[0]
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except Exception:
                tool_args = {}
            return thought, tool_name, tool_args

        return thought, "browser_get_page_content", {}
