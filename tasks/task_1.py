"""Task 1: Latest Invoice Entry."""
import asyncio
from env.seed import seed_database
from agent.loop import AgentLoop
from tasks.definitions import get_task

async def run():
    seed_database()
    spec = get_task(1)
    agent = AgentLoop(task=spec.prompt, auto_approve=True, is_cli=True)
    return await agent.run()

if __name__ == "__main__":
    asyncio.run(run())
