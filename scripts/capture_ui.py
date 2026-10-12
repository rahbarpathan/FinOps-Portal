import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from agent.tools import ToolManager

async def capture():
    b = ToolManager(headless=True)
    await b.browser_goto('http://localhost:8000/inbox')
    await b.browser_screenshot('inbox_view.png')
    
    await b.browser_goto('http://localhost:8000/bills')
    await b.browser_screenshot('bills_view.png')
    
    await b.browser_goto('http://localhost:8000/agent')
    await b.browser_screenshot('agent_cockpit_view.png')
    
    await b.close()
    print("All UI screenshots captured successfully!")

if __name__ == '__main__':
    asyncio.run(capture())
