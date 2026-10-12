import os
import sys
import uvicorn
import argparse
from dotenv import load_dotenv

load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="CentrAlign AI FinOps Portal & Autonomous Agent Runner")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--cli", nargs="?", const="Find the latest invoice from Acme Corp, create a bill, and confirm.", help="Run in CLI mode with optional task prompt")
    parser.add_argument("--provider", default="auto", choices=["auto", "gemini", "openai", "anthropic", "offline"], help="LLM Provider")
    parser.add_argument("--reset", action="store_true", help="Force reset of deterministic seed data")

    args = parser.parse_args()

    # Ensure seed data exists
    from src.portal.seed import seed_database
    from src.portal.db import get_connection

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "finops.db")
    if args.reset or not os.path.exists(db_path):
        print("[*] Initializing deterministic seed environment...")
        seed_database()

    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    if args.cli:
        import asyncio
        from src.agent.cli import run_cli_agent
        print(f"[*] Running Autonomous Task Worker CLI with task: '{args.cli}'\n")
        asyncio.run(run_cli_agent(args.cli, args.provider, max_steps=15, do_reset=False))
    else:
        print("\n" + "="*70)
        print("[*] CentrAlign AI - FinOps Portal & Autonomous AI Task Worker")
        print("="*70)
        print(f"Vendor Inbox:           http://localhost:{args.port}/inbox")
        print(f"Finance System (Bills): http://localhost:{args.port}/bills")
        print(f"Agent Live Cockpit:     http://localhost:{args.port}/agent")
        print(f"Ground-Truth Verifier:  http://localhost:{args.port}/api/ground-truth")
        print("="*70)
        print("Press Ctrl+C to stop the server.\n")

        uvicorn.run("src.portal.app:app", host=args.host, port=args.port, reload=False)

if __name__ == "__main__":
    main()
