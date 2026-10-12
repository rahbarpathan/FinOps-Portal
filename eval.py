"""
Evaluation Suite for Autonomous AI Task Worker.
Runs all 5 core benchmark tasks against freshly reset environments,
validates outcomes independently against ground-truth state,
and displays a rich performance table.
"""
import os
import sys
import time
import json
import asyncio
import httpx
import uvicorn
import threading
from typing import Dict, Any, List

# Ensure repository root is on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from env.seed import seed_database
from env.db import get_connection, set_config
from agent.loop import AgentLoop
from tasks.definitions import TASKS, TaskSpec

PORTAL_URL = "http://127.0.0.1:8000"

import subprocess

def ensure_server_running():
    """Verify mock portal is listening; start background server subprocess if needed."""
    try:
        with httpx.Client(timeout=1.5) as client:
            res = client.get(f"{PORTAL_URL}/api/ground-truth")
            if res.status_code == 200:
                return None
    except Exception:
        pass

    print("[*] Starting local FinOps Portal server on 127.0.0.1:8000 in background...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "env.app:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Wait for server to become responsive
    for _ in range(30):
        time.sleep(0.3)
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.get(f"{PORTAL_URL}/api/ground-truth")
                if res.status_code == 200:
                    print("[*] FinOps Portal server is online and healthy.\n")
                    return proc
        except Exception:
            continue

    print("[!] Warning: Could not verify server responsiveness on 127.0.0.1:8000.")
    return proc

async def run_single_task(spec: TaskSpec) -> Dict[str, Any]:
    """Execute a single benchmark task in a freshly reset environment."""
    print(f"\n{'='*70}")
    print(f"[*] Running Task {spec.id}: {spec.name}")
    print(f"    Prompt: '{spec.prompt}'")
    print(f"    Category: {spec.category}")
    print(f"{'='*70}")

    # 1. Fresh deterministic environment reset
    seed_database()

    # 2. Configure failure injection if required
    if spec.inject_failure == "fail_500":
        print(f"    [Chaos Mode] Activating failure injection: '{spec.inject_failure}'")
        set_config("fail_500_count", "1")
    else:
        set_config("fail_500_count", "0")

    # 3. Instantiate domain-agnostic agent loop
    agent = AgentLoop(
        task=spec.prompt,
        run_id=f"eval_task_{spec.id}_{int(time.time())}",
        provider="offline",
        max_steps=25,
        is_cli=True,
        auto_approve=spec.auto_approve
    )

    start_time = time.time()
    result = await agent.run()
    elapsed = time.time() - start_time

    ver = result.get("verification", {})
    is_verified = ver.get("is_verified", False) if ver else result.get("success", False)

    return {
        "task_id": spec.id,
        "name": spec.name,
        "category": spec.category,
        "prompt": spec.prompt,
        "success": is_verified,
        "status": result.get("status", "unverified"),
        "summary": result.get("summary", ""),
        "steps": result.get("steps", 0),
        "retries": result.get("retries", 0),
        "approvals": result.get("approvals", 0),
        "time_seconds": round(elapsed, 2),
        "audit_hash": ver.get("audit_hash", "NONE") if ver else "NONE",
        "checks": ver.get("checks", []) if ver else []
    }

async def run_all_evaluations() -> List[Dict[str, Any]]:
    """Run all 5 tasks sequentially and return results."""
    results = []
    for spec in TASKS:
        res = await run_single_task(spec)
        results.append(res)
    return results

def render_results_table(results: List[Dict[str, Any]]):
    """Print beautifully formatted evaluation summary table."""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel

        console = Console()
        console.print("\n")
        console.print(Panel(
            "[bold white]Autonomous AI Task Worker - Ground-Truth Evaluation Report[/bold white]\n"
            "[dim]Evaluated against deterministic FinOps Portal environment with independent verification[/dim]",
            title="CentrAlign AI Evaluation Suite",
            border_style="cyan"
        ))

        table = Table(title="Benchmark Results Summary", border_style="dim", header_style="bold magenta")
        table.add_column("ID", justify="center", style="dim", width=4)
        table.add_column("Task Name", style="bold cyan", min_width=22)
        table.add_column("Ground-Truth Verified", justify="center", min_width=18)
        table.add_column("Status", justify="center", min_width=10)
        table.add_column("Steps", justify="right", width=6)
        table.add_column("Retries", justify="right", width=8)
        table.add_column("Approvals", justify="right", width=10)
        table.add_column("Time (s)", justify="right", width=9)
        table.add_column("Audit Hash", style="yellow", min_width=20)

        all_passed = True
        total_steps = 0
        total_retries = 0
        total_approvals = 0
        total_time = 0.0

        for r in results:
            passed = r["success"]
            if not passed:
                all_passed = False
            total_steps += r["steps"]
            total_retries += r["retries"]
            total_approvals += r["approvals"]
            total_time += r["time_seconds"]

            status_str = f"[green]PASSED[/green]" if passed else f"[red]FAILED[/red]"
            badge_str = f"[bold green]{r['status'].upper()}[/bold green]" if passed else f"[bold red]{r['status'].upper()}[/bold red]"

            table.add_row(
                str(r["task_id"]),
                r["name"],
                status_str,
                badge_str,
                str(r["steps"]),
                str(r["retries"]),
                str(r["approvals"]),
                f"{r['time_seconds']:.2f}",
                r["audit_hash"]
            )

        console.print(table)

        summary_box = (
            f"[bold]{'ALL TASKS PASSED' if all_passed else 'EVALUATION HAD FAILURES'}[/bold]\n"
            f"Total Tasks: {len(results)} | Passed: {sum(1 for r in results if r['success'])}/{len(results)}\n"
            f"Total Execution Steps: {total_steps} | Total Retries: {total_retries} | Total Approvals Gated: {total_approvals}\n"
            f"Total Runtime: {total_time:.2f}s"
        )
        box_style = "green" if all_passed else "red"
        console.print(Panel(summary_box, title="Evaluation Verdict", border_style=box_style))

    except ImportError:
        # Fallback standard printing if rich is missing
        print("\n" + "="*85)
        print(f"{'ID':<4} {'Task Name':<28} {'Verified':<10} {'Steps':<6} {'Retries':<8} {'Approvals':<10} {'Time':<8} {'Audit Hash'}")
        print("="*85)
        for r in results:
            print(f"{r['task_id']:<4} {r['name']:<28} {'PASS' if r['success'] else 'FAIL':<10} {r['steps']:<6} {r['retries']:<8} {r['approvals']:<10} {r['time_seconds']:<8.2f} {r['audit_hash']}")
        print("="*85)

def main():
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    server = ensure_server_running()

    try:
        results = asyncio.run(run_all_evaluations())
        render_results_table(results)

        # Write summary JSON to runs/eval_summary.json
        runs_dir = os.path.join(BASE_DIR, "runs")
        os.makedirs(runs_dir, exist_ok=True)
        eval_path = os.path.join(runs_dir, "eval_summary.json")
        with open(eval_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "total_tasks": len(results),
                "passed_count": sum(1 for r in results if r["success"]),
                "results": results
            }, f, indent=2)
        print(f"\n[*] Evaluation results saved to {eval_path}")

        # Exit with error code if any task failed
        if not all(r["success"] for r in results):
            sys.exit(1)

    finally:
        pass

if __name__ == "__main__":
    main()
