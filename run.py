"""
CentrAlign AI FinOps Portal & Autonomous AI Task Worker CLI / Server Runner.
"""
import os
import sys
import asyncio
import uvicorn
import argparse
from dotenv import load_dotenv

load_dotenv()

# Ensure repository root is on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from env.seed import seed_database
from env.db import get_connection

TASKS_MAP = {
    "1": "Find the latest invoice from Acme Corp, extract the amount and due date, enter it into the finance system, and tell me once it's done.",
    "2": "Mark the bill for invoice INV-INI-001 as paid.",
    "3": "List all bills due in the next 7 days and write a summary to summary.md.",
    "4": "Process the invoice from Acme",
    "5": "Find the latest invoice from Globex Corp, enter it into the finance system, and verify."
}

async def run_cli_task(task_text: str, provider: str = "auto", auto_approve: bool = False, max_steps: int = 30):
    from agent.loop import AgentLoop
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    console.print(Panel(f"[bold cyan]Task Objective:[/bold cyan] {task_text}", title="CentrAlign AI Autonomous Task Worker", border_style="cyan"))

    agent = AgentLoop(
        task=task_text,
        provider=provider,
        max_steps=max_steps,
        is_cli=True,
        auto_approve=auto_approve
    )

    console.print("[dim]Starting ReAct autonomous execution loop...[/dim]\n")
    result = await agent.run()

    console.print("\n" + "=" * 60)
    status_color = "green" if result.get("success") else "red"
    console.print(f"[{status_color}]Outcome Status: {result.get('status', 'unknown').upper()}[/{status_color}]")
    console.print(f"Summary: {result.get('summary')}")
    console.print(f"Steps: {result.get('steps')} | Retries: {result.get('retries')} | Approvals: {result.get('approvals')} | Time: {result.get('time_seconds')}s")

    ver = result.get("verification")
    if ver:
        console.print(f"Audit Proof: [bold yellow]{ver.get('audit_hash', 'N/A')}[/bold yellow]")
        if ver.get("checks"):
            table = Table(title="Independent Ground-Truth Verification Checks", border_style="dim")
            table.add_column("Criterion", style="cyan")
            table.add_column("Expected", style="dim")
            table.add_column("Actual", style="dim")
            table.add_column("Pass", justify="center")
            for c in ver["checks"]:
                table.add_row(
                    c.get("criterion", ""),
                    str(c.get("expected", "")),
                    str(c.get("actual", "")),
                    "[green]PASS[/green]" if c.get("passed") else "[red]FAIL[/red]"
                )
            console.print(table)
    console.print("=" * 60)
    return result

def main():
    parser = argparse.ArgumentParser(description="CentrAlign AI FinOps Portal & Autonomous Agent Runner")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"), help="Server host")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")), help="Server port")
    parser.add_argument("--cli", nargs="?", const="Find the latest invoice from Acme Corp, extract the amount and due date, enter it into the finance system, and tell me once it's done.", help="Run in CLI mode with optional task prompt")
    parser.add_argument("--task", choices=["1", "2", "3", "4", "5"], help="Run a specific benchmark evaluation task number (1-5)")
    parser.add_argument("--provider", default="auto", choices=["auto", "groq", "gemini", "openai", "anthropic", "offline"], help="LLM Provider")
    parser.add_argument("--auto-approve", action="store_true", help="Auto-approve sensitive side-effect actions (for headless/eval runs)")
    parser.add_argument("--reset", action="store_true", help="Force reset of deterministic seed data")

    args = parser.parse_args()

    db_path = os.path.join(BASE_DIR, "data", "finops.db")
    if args.reset or not os.path.exists(db_path):
        print("[*] Initializing deterministic seed environment...")
        seed_database()

    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    if args.task:
        task_prompt = TASKS_MAP[args.task]
        print(f"[*] Executing Benchmark Task {args.task}: '{task_prompt}'\n")
        if args.task == "5":
            from env.db import set_config
            set_config("fail_500_count", "1")
        asyncio.run(run_cli_task(task_prompt, provider=args.provider, auto_approve=args.auto_approve or (args.task in ["1", "3", "5"])))
    elif args.cli:
        print(f"[*] Running Autonomous Task Worker CLI with task: '{args.cli}'\n")
        asyncio.run(run_cli_task(args.cli, provider=args.provider, auto_approve=args.auto_approve))
    else:
        print("\n" + "=" * 70)
        print("[*] CentrAlign AI - FinOps Portal & Autonomous AI Task Worker")
        print("=" * 70)
        print(f"Vendor Inbox:           http://localhost:{args.port}/inbox")
        print(f"Finance System (Bills): http://localhost:{args.port}/bills")
        print(f"Agent Live Cockpit:     http://localhost:{args.port}/agent")
        print(f"Ground-Truth Verifier:  http://localhost:{args.port}/api/ground-truth")
        print("=" * 70)
        print("Press Ctrl+C to stop the server.\n")

        uvicorn.run("env.app:app", host=args.host, port=args.port, reload=False)

if __name__ == "__main__":
    main()
