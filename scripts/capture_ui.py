import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from src.agent.tools.browser import BrowserController

async def capture():
    b = BrowserController(headless=True)
    await b.navigate('http://localhost:8000/inbox')
    await b.take_screenshot('inbox_view.png')
    
    await b.navigate('http://localhost:8000/bills')
    await b.take_screenshot('bills_view.png')
    
    await b.navigate('http://localhost:8000/agent')
    await b.take_screenshot('agent_cockpit_view.png')
    
    await b.close()
    print("All UI screenshots captured successfully!")

if __name__ == '__main__':
    asyncio.run(capture())
