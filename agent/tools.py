"""
Generic, domain-agnostic tool definitions for the autonomous AI task worker.
Includes browser accessibility-tree snapshotting, element-ref interactions,
file system tools, HTTP requests, scratchpad memory, and human approval gates.
"""
import os
import sys
import json
import asyncio
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from playwright.async_api import async_playwright, Browser, Page, Playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "artifacts", "screenshots")
RUNS_DIR = os.path.join(BASE_DIR, "runs")

class ToolManager:
    """
    Manages Playwright browser, file I/O, HTTP requests, and interaction tools.
    """
    def __init__(self, headless: Optional[bool] = None, run_id: str = "run"):
        self.headless = headless if headless is not None else os.getenv("BROWSER_HEADLESS", "true").lower() in ("true", "1")
        self.run_id = run_id

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        # Ref map maps "e1", "e2" -> selector or element metadata
        self._ref_map: Dict[str, Dict[str, Any]] = {}

        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        os.makedirs(RUNS_DIR, exist_ok=True)

    def _get_executable_path(self) -> Optional[str]:
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return None

    async def ensure_browser(self):
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
            self._browser = await self._playwright.chromium.launch(headless=self.headless)

        context = await self._browser.new_context(viewport={"width": 1280, "height": 900})
        self._page = await context.new_page()

    # 1. browser_goto(url)
    async def browser_goto(self, url: str) -> Dict[str, Any]:
        await self.ensure_browser()
        try:
            res = await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(0.4)
            status_code = res.status if res else 200
            title = await self._page.title()
            return {
                "success": status_code < 400,
                "url": self._page.url,
                "status_code": status_code,
                "title": title
            }
        except Exception as e:
            return {"success": False, "error": f"Navigation failed: {str(e)}"}

    # 2. browser_snapshot(): returns accessibility tree / simplified DOM with refs
    async def browser_snapshot(self) -> Dict[str, Any]:
        await self.ensure_browser()
        url = self._page.url
        title = await self._page.title()
        self._ref_map.clear()
        ref_counter = 1

        tree_lines = [f"PAGE: '{title}' | URL: {url}"]

        # Alerts
        for el in await self._page.query_selector_all(".alert, [role='alert']"):
            if await el.is_visible():
                txt = (await el.inner_text()).strip()
                if txt:
                    tree_lines.append(f"  [ALERT] {txt}")

        # Headings
        for el in await self._page.query_selector_all("h1, h2, h3"):
            if await el.is_visible():
                txt = (await el.inner_text()).strip()
                if txt:
                    tree_lines.append(f"  [HEADING] {txt}")

        # Interactive elements: links, buttons, inputs, selects, textareas
        interactive_selectors = [
            ("button", "button, input[type='submit']"),
            ("link", "a"),
            ("input", "input:not([type='hidden']), textarea"),
            ("select", "select")
        ]

        for kind, query in interactive_selectors:
            elements = await self._page.query_selector_all(query)
            for el in elements:
                if await el.is_visible():
                    ref = f"e{ref_counter}"
                    ref_counter += 1

                    el_id = await el.get_attribute("id") or ""
                    el_name = await el.get_attribute("name") or ""
                    el_text = (await el.inner_text()).strip() if kind in ("button", "link") else ""
                    val = await el.input_value() if kind in ("input", "select") and hasattr(el, 'input_value') else ""
                    placeholder = await el.get_attribute("placeholder") or ""
                    data_test = await el.get_attribute("data-testid") or ""

                    desc_parts = [f"[ref={ref}] {kind.upper()}"]
                    if el_text: desc_parts.append(f"'{el_text[:50]}'")
                    if el_id: desc_parts.append(f"id='{el_id}'")
                    if el_name: desc_parts.append(f"name='{el_name}'")
                    if placeholder: desc_parts.append(f"placeholder='{placeholder}'")
                    if kind in ("input", "select"): desc_parts.append(f"current_val='{val}'")

                    tree_lines.append(f"  {' '.join(desc_parts)}")

                    # Store in ref map
                    best_selector = f"#{el_id}" if el_id else f"[name='{el_name}']" if el_name else None
                    if not best_selector and el_text:
                        best_selector = f"text='{el_text}'"
                    if not best_selector:
                        best_selector = query

                    self._ref_map[ref] = {
                        "kind": kind,
                        "id": el_id,
                        "name": el_name,
                        "text": el_text,
                        "selector": best_selector,
                        "handle": el
                    }

        # Table data rows
        rows = await self._page.query_selector_all("tbody tr")
        for row in rows[:10]:
            if await row.is_visible():
                cells = await row.query_selector_all("td")
                txt = " | ".join([(await c.inner_text()).strip() for c in cells])
                if txt:
                    tree_lines.append(f"  [ROW] {txt}")

        snapshot_str = "\n".join(tree_lines)
        return {
            "success": True,
            "url": url,
            "title": title,
            "accessibility_tree": snapshot_str,
            "ref_count": len(self._ref_map)
        }

    def _resolve_ref(self, target: str) -> Optional[str]:
        target = target.strip()
        if target in self._ref_map:
            return self._ref_map[target]["selector"]
        # If passed without "ref=" or element ID
        for k, v in self._ref_map.items():
            if target == k or target == v.get("id") or target == v.get("name") or target in v.get("text", ""):
                return v["selector"]
        return target

    # 3. browser_click(ref)
    async def browser_click(self, ref: str) -> Dict[str, Any]:
        await self.ensure_browser()
        resolved = self._resolve_ref(ref)

        candidates = [
            resolved,
            f"#{resolved}" if not resolved.startswith("#") else resolved,
            f"text={ref}",
            f"button:has-text('{ref}')",
            f"a:has-text('{ref}')",
            f"[data-testid='{ref}']"
        ]

        last_error = None
        for sel in candidates:
            try:
                el = await self._page.wait_for_selector(sel, timeout=1800, state="visible")
                if el:
                    await el.click()
                    if "submit" in ref.lower():
                        try:
                            await self._page.wait_for_load_state("domcontentloaded", timeout=4000)
                        except Exception:
                            pass
                    await asyncio.sleep(0.5)
                    # Switch page if new tab opened
                    if self._browser and self._browser.contexts and len(self._browser.contexts[0].pages) > 1:
                        self._page = self._browser.contexts[0].pages[-1]
                    return {
                        "success": True,
                        "clicked": ref,
                        "current_url": self._page.url,
                        "title": await self._page.title()
                    }
            except Exception as e:
                last_error = e

        return {
            "success": False,
            "error": f"Element '{ref}' not found or unclickable. (Error: {str(last_error)})",
            "url": self._page.url
        }

    # 4. browser_type(ref, text)
    async def browser_type(self, ref: str, text: str) -> Dict[str, Any]:
        await self.ensure_browser()
        resolved = self._resolve_ref(ref)

        candidates = [
            resolved,
            f"#{resolved}" if not resolved.startswith("#") else resolved,
            f"[name='{resolved}']",
            f"[placeholder*='{resolved}']"
        ]

        last_error = None
        for sel in candidates:
            try:
                el = await self._page.wait_for_selector(sel, timeout=1800, state="visible")
                if el:
                    await el.fill(str(text))
                    return {
                        "success": True,
                        "typed_target": ref,
                        "value": str(text)
                    }
            except Exception as e:
                last_error = e

        return {
            "success": False,
            "error": f"Input field '{ref}' not found to type value '{text}'. (Error: {str(last_error)})"
        }

    # 5. browser_select(ref, option)
    async def browser_select(self, ref: str, option: str) -> Dict[str, Any]:
        await self.ensure_browser()
        resolved = self._resolve_ref(ref)
        try:
            el = await self._page.wait_for_selector(resolved, timeout=1800, state="visible")
            if el:
                await el.select_option(label=option)
                return {"success": True, "selected_option": option}
        except Exception as e:
            return {"success": False, "error": f"Select '{ref}' failed: {str(e)}"}

    # 6. browser_extract_text(ref/selector)
    async def browser_extract_text(self, ref: str) -> Dict[str, Any]:
        await self.ensure_browser()
        resolved = self._resolve_ref(ref)
        try:
            el = await self._page.query_selector(resolved)
            if el:
                txt = (await el.inner_text()).strip()
                return {"success": True, "text": txt}
            return {"success": False, "error": f"Element '{ref}' not found."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # 7. browser_screenshot(filename)
    async def browser_screenshot(self, filename: Optional[str] = None) -> Dict[str, Any]:
        await self.ensure_browser()
        fn = filename or f"evidence_{self.run_id}_{int(datetime.now().timestamp())}.png"
        if not fn.endswith(".png"): fn += ".png"
        filepath = os.path.join(SCREENSHOTS_DIR, fn)
        try:
            await self._page.screenshot(path=filepath, full_page=True)
            return {
                "success": True,
                "filepath": filepath,
                "url": f"/artifacts/screenshots/{fn}"
            }
        except Exception as e:
            return {"success": False, "error": f"Screenshot failed: {str(e)}"}

    # 8. read_file(path)
    def read_file(self, path: str) -> Dict[str, Any]:
        full_path = os.path.join(BASE_DIR, path) if not os.path.isabs(path) else path
        if not os.path.exists(full_path):
            return {"success": False, "error": f"File '{path}' does not exist."}
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return {"success": True, "path": path, "content": content, "size": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # 9. write_file(path, content)
    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        full_path = os.path.join(BASE_DIR, path) if not os.path.isabs(path) else path
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": path, "bytes_written": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # 10. list_files(dir)
    def list_files(self, directory: str = ".") -> Dict[str, Any]:
        full_dir = os.path.join(BASE_DIR, directory) if not os.path.isabs(directory) else directory
        if not os.path.exists(full_dir):
            return {"success": False, "error": f"Directory '{directory}' does not exist."}
        try:
            entries = []
            for name in os.listdir(full_dir):
                p = os.path.join(full_dir, name)
                entries.append({"name": name, "is_dir": os.path.isdir(p), "size": os.path.getsize(p) if os.path.isfile(p) else 0})
            return {"success": True, "directory": directory, "files": entries}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # 11. http_request(method, url, body)
    async def http_request(self, method: str, url: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                m = method.upper()
                if m == "GET":
                    res = await client.get(url)
                elif m == "POST":
                    res = await client.post(url, json=body or {})
                elif m == "PUT":
                    res = await client.put(url, json=body or {})
                elif m == "DELETE":
                    res = await client.delete(url)
                else:
                    return {"success": False, "error": f"Unsupported method: {method}"}

                try:
                    data = res.json()
                except Exception:
                    data = res.text

                return {
                    "success": res.status_code < 400,
                    "status_code": res.status_code,
                    "response": data
                }
        except Exception as e:
            return {"success": False, "error": f"HTTP request failed: {str(e)}"}

    async def close(self):
        try:
            if self._page: await self._page.close()
            if self._browser: await self._browser.close()
            if self._playwright: await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._page = None
            self._browser = None
            self._playwright = None
