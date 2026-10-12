"""Task 5: Failure Injection Recovery."""
import asyncio
from env.seed import seed_database
from env.db import set_config
from agent.loop import AgentLoop
from tasks.definitions import get_task

async def run():
    seed_database()
    # Inject HTTP 500 transient failure on first submission
    set_config("fail_500_count", "1")
    spec = get_task(5)
    agent = AgentLoop(task=spec.prompt, auto_approve=True, is_cli=True)
    return await agent.run()

if __name__ == "__main__":
    asyncio.run(run())
