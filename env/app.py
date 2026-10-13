"""
FinOps Portal FastAPI Server.
Provides Vendor Inbox, Internal Finance System (Bills), Failure Injection Sandbox,
and Ground-Truth State isolation.
"""
import os
import re
import time
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from env.db import get_connection, init_db, get_config, set_config
from env.seed import seed_database

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "artifacts", "screenshots")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="CentrAlign FinOps Portal",
    description="Mock enterprise environment for autonomous task worker",
    lifespan=lifespan
)

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/artifacts/screenshots", StaticFiles(directory=SCREENSHOTS_DIR), name="screenshots")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Broker for SSE streams and approval futures
active_runs: Dict[str, Dict[str, Any]] = {}

@app.get("/", response_class=HTMLResponse)
def index_redirect():
    return RedirectResponse(url="/inbox")

@app.get("/invoices", response_class=HTMLResponse)
@app.get("/invoice", response_class=HTMLResponse)
def invoices_alias():
    return RedirectResponse(url="/inbox")

# ----------------- Vendor Inbox -----------------

@app.get("/inbox", response_class=HTMLResponse)
def view_inbox(request: Request):
    conn = get_connection()
    emails = conn.execute("SELECT * FROM inbox_emails ORDER BY id ASC").fetchall()
    conn.close()
    return templates.TemplateResponse(request=request, name="inbox.html", context={
        "active_page": "inbox",
        "emails": [dict(e) for e in emails]
    })

@app.get("/inbox/attachment/{email_id}", response_class=HTMLResponse)
def view_attachment(request: Request, email_id: int):
    conn = get_connection()
    email = conn.execute("SELECT * FROM inbox_emails WHERE id = ?", (email_id,)).fetchone()
    conn.close()

    if not email:
        raise HTTPException(status_code=404, detail="Email attachment not found")

    raw_content = ""
    if os.path.exists(email["attachment_path"]):
        with open(email["attachment_path"], "r", encoding="utf-8", errors="ignore") as f:
            raw_content = f.read()
    else:
        raw_content = f"[Attachment file not found at {email['attachment_path']}]"

    return templates.TemplateResponse(request=request, name="attachment_view.html", context={
        "active_page": "inbox",
        "email": dict(email),
        "raw_content": raw_content
    })

# ----------------- Internal Finance System / Bills -----------------

@app.get("/bills", response_class=HTMLResponse)
def list_bills(request: Request):
    conn = get_connection()
    bills = conn.execute("SELECT * FROM finance_bills ORDER BY id DESC").fetchall()
    conn.close()
    return templates.TemplateResponse(request=request, name="bills.html", context={
        "active_page": "bills",
        "bills": [dict(b) for b in bills]
    })

@app.get("/bills/create", response_class=HTMLResponse)
def create_bill_page(
    request: Request,
    vendor: Optional[str] = None,
    invoice: Optional[str] = None,
    amount: Optional[str] = None,
    due_date: Optional[str] = None,
    fail_once: Optional[str] = None,
    alt_layout: Optional[str] = None,
    validation_error_once: Optional[str] = None,
    slow: Optional[str] = None
):
    if fail_once:
        set_config("fail_500_count", "1")
    if alt_layout:
        set_config("alt_layout", "1" if alt_layout.lower() in ("1", "true") else "0")
    if validation_error_once:
        set_config("validation_error_count", "1")
    if slow:
        set_config("slow_seconds", str(float(slow)))

    fail_500_active = int(get_config("fail_500_count", "0")) > 0
    val_err_active = int(get_config("validation_error_count", "0")) > 0
    alt_layout_active = int(get_config("alt_layout", "0")) > 0
    slow_seconds = float(get_config("slow_seconds", "0"))

    if slow_seconds > 0:
        time.sleep(slow_seconds)

    prefill = {"vendor": vendor, "invoice": invoice, "amount": amount, "due_date": due_date}

    return templates.TemplateResponse(request=request, name="create_bill.html", context={
        "active_page": "create_bill",
        "prefill": prefill,
        "fail_500_active": fail_500_active,
        "val_err_active": val_err_active,
        "alt_layout_active": alt_layout_active,
        "error": None,
        "success": False
    })

@app.post("/bills/create", response_class=HTMLResponse)
def submit_bill(
    request: Request,
    vendor: str = Form(...),
    invoice_number: str = Form(...),
    amount: str = Form(...),
    due_date: str = Form(...),
    notes: Optional[str] = Form(None)
):
    # Failure injections
    fail_500_count = int(get_config("fail_500_count", "0"))
    if fail_500_count > 0:
        set_config("fail_500_count", str(fail_500_count - 1))
        return templates.TemplateResponse(request=request, name="create_bill.html", context={
            "active_page": "create_bill",
            "prefill": {"vendor": vendor, "invoice": invoice_number, "amount": amount, "due_date": due_date, "notes": notes},
            "fail_500_active": False,
            "val_err_active": False,
            "alt_layout_active": int(get_config("alt_layout", "0")) > 0,
            "error": "Internal Server Error 500: Database transaction lock timeout (Injected Failure to verify Agent Retry Recovery)",
            "success": False
        }, status_code=500)

    val_err_count = int(get_config("validation_error_count", "0"))
    if val_err_count > 0:
        set_config("validation_error_count", str(val_err_count - 1))
        return templates.TemplateResponse(request=request, name="create_bill.html", context={
            "active_page": "create_bill",
            "prefill": {"vendor": vendor, "invoice": invoice_number, "amount": amount, "due_date": due_date, "notes": notes},
            "fail_500_active": False,
            "val_err_active": False,
            "alt_layout_active": int(get_config("alt_layout", "0")) > 0,
            "error": "Validation Error (First Attempt): Vendor tax authorization code is required in notes before initial filing.",
            "success": False
        }, status_code=400)

    # 1. Validation Rule: Due Date must be YYYY-MM-DD
    due_date_clean = due_date.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", due_date_clean):
        return templates.TemplateResponse(request=request, name="create_bill.html", context={
            "active_page": "create_bill",
            "prefill": {"vendor": vendor, "invoice": invoice_number, "amount": amount, "due_date": due_date, "notes": notes},
            "fail_500_active": False,
            "val_err_active": False,
            "alt_layout_active": int(get_config("alt_layout", "0")) > 0,
            "error": f"Invalid due date format '{due_date}'. System strictly requires YYYY-MM-DD (e.g. 2024-06-10).",
            "success": False
        }, status_code=400)

    # 2. Validation Rule: Amount must be numeric
    amount_str = amount.strip()
    try:
        amount_val = float(amount_str)
        if amount_val <= 0:
            raise ValueError("Amount must be positive")
    except ValueError:
        return templates.TemplateResponse(request=request, name="create_bill.html", context={
            "active_page": "create_bill",
            "prefill": {"vendor": vendor, "invoice": invoice_number, "amount": amount, "due_date": due_date, "notes": notes},
            "fail_500_active": False,
            "val_err_active": False,
            "alt_layout_active": int(get_config("alt_layout", "0")) > 0,
            "error": f"Invalid amount format '{amount}'. Amount must be a positive numeric value without currency symbols or commas (e.g. 8250.00).",
            "success": False
        }, status_code=400)

    # 3. Validation Rule: Duplicate invoice numbers are rejected
    conn = get_connection()
    cursor = conn.cursor()
    existing = cursor.execute("SELECT id FROM finance_bills WHERE invoice_number = ?", (invoice_number.strip(),)).fetchone()
    if existing:
        conn.close()
        return templates.TemplateResponse(request=request, name="create_bill.html", context={
            "active_page": "create_bill",
            "prefill": {"vendor": vendor, "invoice": invoice_number, "amount": amount, "due_date": due_date, "notes": notes},
            "fail_500_active": False,
            "val_err_active": False,
            "alt_layout_active": int(get_config("alt_layout", "0")) > 0,
            "error": f"Duplicate Invoice: A bill with invoice reference '{invoice_number.strip()}' has already been registered in the finance system (Bill #{existing['id']}).",
            "success": False
        }, status_code=400)

    # Insert valid bill
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO finance_bills (vendor, invoice_number, amount, due_date, notes, status, created_at)
    VALUES (?, ?, ?, ?, ?, 'Pending', ?)
    """, (vendor.strip(), invoice_number.strip(), amount_val, due_date_clean, notes or "", now_str))
    bill_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/bills/{bill_id}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/bills/{bill_id}", response_class=HTMLResponse)
def view_bill(request: Request, bill_id: int):
    conn = get_connection()
    bill = conn.execute("SELECT * FROM finance_bills WHERE id = ?", (bill_id,)).fetchone()
    conn.close()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return templates.TemplateResponse(request=request, name="bill_detail.html", context={
        "active_page": "bills",
        "bill": dict(bill)
    })

@app.post("/bills/{bill_id}/status")
def update_bill_status(bill_id: int, status: str = Form(...)):
    conn = get_connection()
    conn.execute("UPDATE finance_bills SET status = ? WHERE id = ?", (status, bill_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/bills/{bill_id}", status_code=303)

# ----------------- Ground Truth (Isolated Verifier API) -----------------

@app.get("/api/ground-truth")
def get_ground_truth_state():
    """
    Ground-truth state endpoint.
    STRICTLY ISOLATED: Used ONLY by the Independent Verifier, NOT by the acting loop!
    """
    conn = get_connection()
    bills = [dict(b) for b in conn.execute("SELECT * FROM finance_bills ORDER BY id ASC").fetchall()]
    emails = [dict(e) for e in conn.execute("SELECT id, vendor, invoice_number, invoice_date, invoice_due_date, invoice_amount FROM inbox_emails").fetchall()]
    conn.close()

    return {
        "timestamp": datetime.now().isoformat(),
        "bills_count": len(bills),
        "bills": bills,
        "emails_count": len(emails),
        "emails": emails,
        "seed_signature": "CENTRALIGN_FINOPS_SEED_OK"
    }

# ----------------- Chaos Injection & Deterministic Reset API -----------------

@app.post("/api/chaos")
async def configure_chaos(request: Request):
    data = await request.json()
    action = data.get("action", "")

    if action == "fail_500":
        set_config("fail_500_count", "1")
    elif action == "validation_err":
        set_config("validation_error_count", "1")
    elif action == "alt_layout":
        current = int(get_config("alt_layout", "0"))
        set_config("alt_layout", "0" if current else "1")
    elif action == "slow":
        set_config("slow_seconds", "3.0")
    elif action == "clear":
        set_config("fail_500_count", "0")
        set_config("validation_error_count", "0")
        set_config("alt_layout", "0")
        set_config("slow_seconds", "0")

    return {
        "success": True,
        "fail_500": get_config("fail_500_count", "0"),
        "validation_err": get_config("validation_error_count", "0"),
        "alt_layout": get_config("alt_layout", "0"),
        "slow_seconds": get_config("slow_seconds", "0")
    }

@app.post("/api/reset")
def reset_environment():
    seed_database()
    return {"success": True, "message": "Environment successfully reset to deterministic seed state."}

# ----------------- Agent Cockpit & Streaming API -----------------

@app.get("/agent", response_class=HTMLResponse)
def agent_cockpit(request: Request):
    return templates.TemplateResponse(request=request, name="agent.html", context={
        "active_page": "agent"
    })

@app.post("/api/agent/run")
async def start_agent_run(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    task = data.get("task", "")
    provider = data.get("provider", "auto")

    import uuid
    run_id = str(uuid.uuid4())[:8]

    queue = asyncio.Queue()
    active_runs[run_id] = {
        "task": task,
        "provider": provider,
        "queue": queue,
        "approval_future": None,
        "finished": False
    }

    from agent.loop import AgentLoop
    agent = AgentLoop(run_id=run_id, task=task, provider=provider, event_queue=queue)
    background_tasks.add_task(agent.run)

    return {"success": True, "run_id": run_id}

@app.get("/api/agent/stream/{run_id}")
async def stream_agent_events(run_id: str):
    run = active_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run ID not found")

    queue: asyncio.Queue = run["queue"]

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=20.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "completed":
                    break
            except asyncio.TimeoutError:
                yield f": keep-alive\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/agent/approval/{run_id}")
async def submit_human_approval(run_id: str, request: Request):
    run = active_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    data = await request.json()
    approved = data.get("approved", False)

    fut = run.get("approval_future")
    if fut and not fut.done():
        fut.set_result(approved)
        return {"success": True, "approved": approved}
    return {"success": False, "message": "No pending approval for this run"}
