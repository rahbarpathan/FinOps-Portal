import os
import json
from typing import Dict, Any, List, Tuple
from src.agent.llm.base import BaseLLMProvider, AGENT_TOOLS_SCHEMA

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def decide_next_step(
        self,
        task: str,
        history: List[Dict[str, Any]],
        working_memory: Dict[str, Any],
        page_summary: Dict[str, Any]
    ) -> Tuple[str, str, Dict[str, Any]]:
        # System instructions and prompt
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

        prompt = f"""
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

Based on the objective, memory, and current browser state, what is your next reasoning step and tool call?
"""

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            
            # Format functions for Gemini
            tools_spec = []
            for t in AGENT_TOOLS_SCHEMA:
                tools_spec.append(types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=t["parameters"]
                ))

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[types.Tool(function_declarations=tools_spec)],
                temperature=0.1
            )

            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config
            )

            # Check for function calls
            thought = response.text or "Analyzing next operational action."
            if response.function_calls:
                fn_call = response.function_calls[0]
                tool_name = fn_call.name
                tool_args = dict(fn_call.args) if fn_call.args else {}
                return thought, tool_name, tool_args

            # If no function call returned in text, parse fallback or navigate
            return thought, "browser_get_page_content", {}

        except Exception as e:
            # If Gemini SDK throws or fails, provide helpful error or fallback
            return f"Gemini API invocation note: {str(e)}", "browser_get_page_content", {}
