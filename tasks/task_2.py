"""Task 2: Mark Bill Paid (Approval Gated)."""
import asyncio
from env.seed import seed_database
from agent.loop import AgentLoop
from tasks.definitions import get_task

async def run(auto_approve: bool = True):
    seed_database()
    spec = get_task(2)
    agent = AgentLoop(task=spec.prompt, auto_approve=auto_approve, is_cli=True)
    return await agent.run()

if __name__ == "__main__":
    asyncio.run(run())
