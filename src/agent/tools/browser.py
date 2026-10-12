import os
import asyncio
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, Page, Playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "artifacts", "screenshots")

class BrowserController:
    """
    Async Playwright Chromium browser controller with resilient selector resolution
    and automatic detection of system-installed Chrome/Edge.
    """
    def __init__(self, headless: Optional[bool] = None):
        if headless is None:
            self.headless = os.getenv("BROWSER_HEADLESS", "true").lower() in ("true", "1")
        else:
            self.headless = headless

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    def _get_executable_path(self) -> Optional[str]:
        # Check standard Windows paths for Chrome and Edge
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return None

    async def start(self):
        if self._page is not None:
            return

        self._playwright = await async_playwright().start()
        exec_path = self._get_executable_path()

        launch_args = ["--disable-blink-features=AutomationControlled"]
        try:
            if exec_path:
                self._browser = await self._playwright.chromium.launch(
                    executable_path=exec_path,
                    headless=self.headless,
                    args=launch_args
                )
            else:
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    args=launch_args
                )
        except Exception:
            # Fallback to standard launch
            self._browser = await self._playwright.chromium.launch(headless=self.headless)

        context = await self._browser.new_context(viewport={"width": 1280, "height": 900})
        self._page = await context.new_page()

    async def ensure_started(self):
        if self._page is None:
            await self.start()

    async def navigate(self, url: str) -> Dict[str, Any]:
        await self.ensure_started()
        try:
            response = await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(0.5)
            status_code = response.status if response else 200
            title = await self._page.title()
            return {
                "success": status_code < 400,
                "url": self._page.url,
                "status_code": status_code,
                "title": title,
                "message": f"Navigated to {url} (HTTP {status_code})"
            }
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": f"Navigation failed: {str(e)}"
            }

    async def get_page_summary(self) -> Dict[str, Any]:
        await self.ensure_started()
        url = self._page.url
        title = await self._page.title()

        # Check for visible error banners or alerts
        alerts = []
        alert_els = await self._page.query_selector_all(".alert, [role='alert']")
        for el in alert_els:
            if await el.is_visible():
                txt = (await el.inner_text()).strip()
                if txt:
                    alerts.append(txt)

        # Extract buttons
        buttons = []
        btn_els = await self._page.query_selector_all("button, input[type='submit'], a.btn")
        for b in btn_els:
            if await b.is_visible():
                txt = (await b.inner_text()).strip() or (await b.get_attribute("value")) or ""
                btn_id = (await b.get_attribute("id")) or ""
                data_test = (await b.get_attribute("data-testid")) or ""
                buttons.append({
                    "text": txt,
                    "id": btn_id,
                    "selector": f"#{btn_id}" if btn_id else f"text='{txt}'",
                    "testid": data_test
                })

        # Extract input fields
        inputs = []
        input_els = await self._page.query_selector_all("input:not([type='hidden']), textarea, select")
        for inp in input_els:
            if await inp.is_visible():
                name = (await inp.get_attribute("name")) or ""
                inp_id = (await inp.get_attribute("id")) or ""
                placeholder = (await inp.get_attribute("placeholder")) or ""
                val = await inp.input_value() if hasattr(inp, 'input_value') else ""
                inputs.append({
                    "id": inp_id,
                    "name": name,
                    "placeholder": placeholder,
                    "current_value": val,
                    "selector": f"#{inp_id}" if inp_id else f"[name='{name}']"
                })

        # Extract table rows if present
        table_rows = []
        row_els = await self._page.query_selector_all("tbody tr")
        for row in row_els:
            if await row.is_visible():
                cells = await row.query_selector_all("td")
                cell_texts = [(await td.inner_text()).strip() for td in cells]
                txt = " | ".join(cell_texts)
                if txt:
                    table_rows.append(txt)

        # Extract main text preview
        body_text = await self._page.inner_text("body")
        lines = [line.strip() for line in body_text.splitlines() if line.strip()]
        preview_text = "\n".join(lines[:35])

        return {
            "url": url,
            "title": title,
            "alerts": alerts,
            "interactive_buttons": buttons,
            "form_inputs": inputs,
            "table_data": table_rows[:8],
            "text_preview": preview_text
        }

    async def click(self, target: str) -> Dict[str, Any]:
        await self.ensure_started()
        target = target.strip()

        candidates = [
            target,
            f"#{target}" if not target.startswith("#") else target,
            f"text={target}",
            f"button:has-text('{target}')",
            f"a:has-text('{target}')",
            f"[data-testid='{target}']",
            f"[id*='{target}']"
        ]

        last_error = None
        for sel in candidates:
            try:
                el = await self._page.wait_for_selector(sel, timeout=1500, state="visible")
                if el:
                    await el.click()
                    await asyncio.sleep(0.6)  # allow form submit or navigation
                    if self._browser and self._browser.contexts and len(self._browser.contexts[0].pages) > 1:
                        self._page = self._browser.contexts[0].pages[-1]
                    return {
                        "success": True,
                        "clicked_selector": sel,
                        "current_url": self._page.url,
                        "title": await self._page.title()
                    }
            except Exception as e:
                last_error = e

        return {
            "success": False,
            "error": f"Failed to click element matching '{target}'. (Last error: {str(last_error)})",
            "page_url": self._page.url
        }

    async def fill(self, selector: str, value: str) -> Dict[str, Any]:
        await self.ensure_started()
        selector = selector.strip()

        candidates = [
            selector,
            f"#{selector}" if not selector.startswith("#") else selector,
            f"[name='{selector}']",
            f"[placeholder*='{selector}']"
        ]

        last_error = None
        for sel in candidates:
            try:
                el = await self._page.wait_for_selector(sel, timeout=1500, state="visible")
                if el:
                    await el.fill(str(value))
                    return {
                        "success": True,
                        "filled_selector": sel,
                        "value": str(value)
                    }
            except Exception as e:
                last_error = e

        return {
            "success": False,
            "error": f"Failed to fill input field '{selector}' with value '{value}'. (Error: {str(last_error)})"
        }

    async def take_screenshot(self, filename: str = "evidence.png") -> Dict[str, Any]:
        await self.ensure_started()
        if not filename.endswith(".png"):
            filename += ".png"
        filepath = os.path.join(SCREENSHOTS_DIR, filename)
        try:
            await self._page.screenshot(path=filepath, full_page=True)
            return {
                "success": True,
                "filepath": filepath,
                "url": f"/artifacts/screenshots/{filename}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Screenshot failed: {str(e)}"
            }

    async def extract_text(self, selector: str) -> Dict[str, Any]:
        await self.ensure_started()
        try:
            el = await self._page.query_selector(selector)
            if el:
                txt = (await el.inner_text()).strip()
                return {"success": True, "text": txt}
            return {"success": False, "error": f"Selector '{selector}' not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self):
        try:
            if self._page:
                await self._page.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._page = None
            self._browser = None
            self._playwright = None
