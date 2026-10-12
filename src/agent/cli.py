import sys
import asyncio
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from dotenv import load_dotenv

from src.agent.core import AutonomousAgent
from src.portal.seed import seed_database

load_dotenv()
console = Console()

async def run_cli_agent(task: str, provider: str, max_steps: int, do_reset: bool):
    if do_reset:
        console.print("[yellow]Resetting FinOps environment to deterministic seed state...[/yellow]")
        seed_database()
        console.print("[green]Environment reset complete.[/green]\n")

    console.print(Panel.fit(
        f"[bold cyan]CentrAlign AI Autonomous Task Worker[/bold cyan]\n"
        f"[bold]Objective:[/bold] {task}\n"
        f"[bold]Provider:[/bold] {provider} | [bold]Max Steps:[/bold] {max_steps}",
        border_style="cyan"
    ))

    # Event queue for console logging
    queue = asyncio.Queue()
    agent = AutonomousAgent(
        run_id="cli-run",
        task=task,
        provider=provider,
        event_queue=queue,
        is_cli=True,
        max_steps=max_steps
    )

    # Consumer task to print live events beautifully
    async def printer():
        while True:
            event = await queue.get()
            t_type = event.get("type")

            if t_type == "step":
                phase = event.get("phase", "")
                step_no = event.get("step_number")
                text = event.get("text", "")
                code = event.get("code", "")

                color = "cyan"
                if phase == "ACTION": color = "blue"
                elif phase == "OBSERVATION": color = "green"
                elif phase == "RECOVERY": color = "magenta"
                elif phase == "HUMAN": color = "yellow"
                elif phase == "VERIFICATION": color = "bold green"

                console.print(f"\n[bold {color}][Step {step_no} - {phase}][/bold {color}] {text}")
                if code:
                    console.print(f"[dim]{code}[/dim]")

            elif t_type == "facts_update":
                facts = event.get("facts", {})
                table = Table(title="Working Memory Facts", show_header=True, header_style="bold magenta")
                table.add_column("Key", style="cyan")
                table.add_column("Discovered Value", style="green")
                for k, v in facts.items():
                    table.add_row(str(k), str(v))
                console.print(table)

            elif t_type == "completed":
                success = event.get("success", False)
                summary = event.get("summary", "")
                v = event.get("verification", {})

                console.print("\n" + "="*60)
                if success:
                    console.print(Panel(
                        f"[bold green]TASK COMPLETED & VERIFIED ✓[/bold green]\n\n"
                        f"[bold]Summary:[/bold] {summary}\n"
                        f"[bold]Audit Hash:[/bold] {v.get('audit_hash')}",
                        border_style="green"
                    ))
                else:
                    console.print(Panel(
                        f"[bold red]TASK FAILED OR UNVERIFIED ✕[/bold red]\n\n"
                        f"[bold]Summary:[/bold] {summary}",
                        border_style="red"
                    ))

                if v and "checks" in v:
                    v_table = Table(title="Independent Ground-Truth Verification", show_header=True)
                    v_table.add_column("Audit Criterion", style="white")
                    v_table.add_column("Result", style="bold")
                    v_table.add_column("Expected", style="dim")
                    v_table.add_column("Actual", style="cyan")

                    for c in v.get("checks", []):
                        res_str = "[green]PASSED[/green]" if c["passed"] else "[red]FAILED[/red]"
                        v_table.add_row(c["criterion"], res_str, str(c["expected"]), str(c["actual"]))
                    console.print(v_table)
                break

    printer_task = asyncio.create_task(printer())
    agent_task = asyncio.create_task(agent.run())

    await asyncio.gather(agent_task, printer_task)

def main():
    parser = argparse.ArgumentParser(description="Autonomous AI Task Worker CLI")
    parser.add_argument("task", nargs="?", default="Find the latest invoice from Acme Corp, compare dates, create a bill in the finance system, and confirm.", help="Natural language objective")
    parser.add_argument("--provider", default="auto", choices=["auto", "gemini", "openai", "anthropic", "offline"], help="LLM Provider")
    parser.add_argument("--max-steps", type=int, default=15, help="Maximum ReAct steps")
    parser.add_argument("--reset", action="store_true", help="Reset portal data before execution")

    args = parser.parse_args()
    asyncio.run(run_cli_agent(args.task, args.provider, args.max_steps, args.reset))

if __name__ == "__main__":
    main()
