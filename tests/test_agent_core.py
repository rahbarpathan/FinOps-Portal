"""
Unit tests for core agent modules:
- Error Classifier (reliability.py)
- Loop Detector (reliability.py)
- Budget Manager (reliability.py)
- Scratchpad Memory & Bounded History (memory.py)
- Safety & Human-in-the-Loop Policy (policy.py)
- Independent Verifier (verifier.py)
"""
import os
import pytest
from agent.reliability import (
    classify_tool_error, is_transient_error,
    ERROR_ELEMENT_NOT_FOUND, ERROR_TIMEOUT, ERROR_VALIDATION,
    ERROR_HTTP_5XX, ERROR_UNEXPECTED_PAGE, ERROR_UNKNOWN,
    LoopDetector, BudgetManager
)
from agent.memory import ScratchpadMemory, BoundedHistory
from agent.policy import SafetyPolicy
from agent.verifier import IndependentVerifier
from env.seed import seed_database
from env.db import get_connection

@pytest.fixture(autouse=True)
def setup_db():
    seed_database()

# -------------------------------------------------------------
# 1. Error Classifier Tests
# -------------------------------------------------------------
def test_error_classifier_http_5xx():
    # Via status code
    assert classify_tool_error("", status_code=500) == ERROR_HTTP_5XX
    assert classify_tool_error("", status_code=503) == ERROR_HTTP_5XX
    # Via error message
    assert classify_tool_error("Internal Server Error") == ERROR_HTTP_5XX
    assert classify_tool_error("Database lock timeout 500 occurred") == ERROR_HTTP_5XX
    # Transient check
    assert is_transient_error(ERROR_HTTP_5XX) is True

def test_error_classifier_timeout():
    assert classify_tool_error("Navigation timed out after 15000ms") == ERROR_TIMEOUT
    assert classify_tool_error("Connection timeout") == ERROR_TIMEOUT
    assert is_transient_error(ERROR_TIMEOUT) is True

def test_error_classifier_element_not_found():
    assert classify_tool_error("waiting for selector '#submit-btn' failed") == ERROR_ELEMENT_NOT_FOUND
    assert classify_tool_error("Element 'pay-btn' not found or unclickable") == ERROR_ELEMENT_NOT_FOUND
    # Element not found is deterministic -> cannot retry naively
    assert is_transient_error(ERROR_ELEMENT_NOT_FOUND) is False

def test_error_classifier_validation_error():
    assert classify_tool_error("Invalid due date format: strictly requires YYYY-MM-DD") == ERROR_VALIDATION
    assert classify_tool_error("Validation error: duplicate invoice number") == ERROR_VALIDATION
    assert is_transient_error(ERROR_VALIDATION) is False

def test_error_classifier_unexpected_page():
    assert classify_tool_error("404 Not Found") == ERROR_UNEXPECTED_PAGE
    assert classify_tool_error("Unexpected page title") == ERROR_UNEXPECTED_PAGE
    assert is_transient_error(ERROR_UNEXPECTED_PAGE) is False

# -------------------------------------------------------------
# 2. Loop Detector Tests
# -------------------------------------------------------------
def test_loop_detector_tracks_and_escalates():
    detector = LoopDetector(repeat_threshold=3)

    # Step 1: Normal action
    is_loop, escalate, msg = detector.record_action("browser_click", {"ref": "submit-btn"})
    assert not is_loop
    assert not escalate

    # Step 2: First repeat (total 2)
    is_loop, escalate, msg = detector.record_action("browser_click", {"ref": "submit-btn"})
    assert not is_loop
    assert not escalate

    # Step 3: Second repeat (total 3 -> reaches threshold of 3 repeats)
    is_loop, escalate, msg = detector.record_action("browser_click", {"ref": "submit-btn"})
    assert is_loop is True
    assert escalate is False
    assert "You MUST change your strategy" in msg

    # Step 4: Third repeat (total 4 -> exceeds threshold, must escalate to ask_user)
    is_loop, escalate, msg = detector.record_action("browser_click", {"ref": "submit-btn"})
    assert is_loop is True
    assert escalate is True
    assert "Escalating to user for guidance" in msg

def test_loop_detector_resets_on_different_action():
    detector = LoopDetector(repeat_threshold=3)
    detector.record_action("browser_click", {"ref": "btn-1"})
    detector.record_action("browser_click", {"ref": "btn-1"})
    # Change action
    is_loop, escalate, _ = detector.record_action("browser_type", {"ref": "notes", "text": "new info"})
    assert not is_loop
    assert not escalate
    assert detector.consecutive_repeats == 1

# -------------------------------------------------------------
# 3. Budget Manager Tests
# -------------------------------------------------------------
def test_budget_manager_step_limit():
    budget = BudgetManager(max_steps=3, max_seconds=10.0)
    assert budget.record_step() == (False, "")
    assert budget.record_step() == (False, "")
    assert budget.record_step() == (False, "")
    is_exceeded, reason = budget.record_step()
    assert is_exceeded is True
    assert "Step budget exceeded" in reason

# -------------------------------------------------------------
# 4. Scratchpad Memory & Bounded History Tests
# -------------------------------------------------------------
def test_scratchpad_memory():
    mem = ScratchpadMemory()
    mem.remember("invoice_id", "INV-ACM-103", source="email_attachment")
    mem.remember("amount", "8250.00", source="email_attachment")

    assert mem.recall("invoice_id") == "INV-ACM-103"
    assert mem.recall("amount") == "8250.00"
    assert mem.recall("nonexistent") is None

    view = mem.render_prompt_view()
    assert "INV-ACM-103" in view
    assert "Source: email_attachment" in view

def test_bounded_history_truncation():
    history = BoundedHistory(max_recent_steps=3)
    for i in range(1, 6):
        history.add_step(i, f"Thought {i}", "browser_click", {"ref": f"e{i}"}, {"success": True})

    rendered = history.render_prompt_history()
    # Should summarize earlier 2 steps
    assert "2 earlier steps summarized" in rendered
    assert "Step 3" in rendered
    assert "Step 4" in rendered
    assert "Step 5" in rendered
    assert "Thought 1" not in rendered  # truncated

# -------------------------------------------------------------
# 5. Safety & Human-in-the-Loop Policy Tests
# -------------------------------------------------------------
def test_safety_policy_identifies_side_effects():
    policy = SafetyPolicy(auto_approve=False)

    # Read-only actions
    assert policy.is_side_effecting_action("browser_goto", {"url": "http://localhost:8000/bills"}) == (False, "")
    assert policy.is_side_effecting_action("browser_snapshot", {}) == (False, "")
    assert policy.is_side_effecting_action("http_request", {"method": "GET", "url": "/api/bills"}) == (False, "")

    # Side-effecting / irreversible mutations
    is_side, reason = policy.is_side_effecting_action("browser_click", {"ref": "submit-bill-btn"})
    assert is_side is True
    assert "persistent state mutation" in reason

    is_side, reason = policy.is_side_effecting_action("browser_click", {"ref": "pay-bill-btn"})
    assert is_side is True

    is_side, reason = policy.is_side_effecting_action("write_file", {"path": "summary.md", "content": "test"})
    assert is_side is True

    is_side, reason = policy.is_side_effecting_action("http_request", {"method": "POST", "url": "/bills/create"})
    assert is_side is True

def test_safety_policy_ambiguity_detection():
    policy = SafetyPolicy()
    is_ambiguous, reason = policy.check_ambiguity("Process the invoice from Acme", ["Acme Corp", "Acme Logistics"])
    assert is_ambiguous is True
    assert "Ambiguous vendor request" in reason

# -------------------------------------------------------------
# 6. Independent Verifier Tests
# -------------------------------------------------------------
def test_verifier_rejects_missing_bill():
    verifier = IndependentVerifier()
    res = verifier.verify_outcome("Find the latest invoice from Acme Corp", {})
    assert res["is_verified"] is False
    assert res["status"] == "failed"
    assert "No bill recorded" in res["summary"]

def test_verifier_rejects_old_invoice():
    # Insert an older invoice (INV-ACM-101 instead of latest INV-ACM-103)
    conn = get_connection()
    conn.execute("""
        INSERT INTO finance_bills (vendor, invoice_number, amount, due_date, notes, status, created_at)
        VALUES ('Acme Corp', 'INV-ACM-101', 1200.00, '2024-02-15', 'Old bill test', 'Pending', '2024-01-16')
    """)
    conn.commit()
    conn.close()

    verifier = IndependentVerifier()
    res = verifier.verify_outcome("Find the latest invoice from Acme Corp", {})
    assert res["is_verified"] is False
    latest_check = next(c for c in res["checks"] if "LATEST invoice" in c["criterion"])
    assert latest_check["passed"] is False

def test_verifier_passes_on_correct_latest_invoice():
    conn = get_connection()
    conn.execute("""
        INSERT INTO finance_bills (vendor, invoice_number, amount, due_date, notes, status, created_at)
        VALUES ('Acme Corp', 'INV-ACM-103', 8250.00, '2024-06-10', 'Latest bill test', 'Pending', '2024-05-11')
    """)
    conn.commit()
    conn.close()

    verifier = IndependentVerifier()
    res = verifier.verify_outcome("Find the latest invoice from Acme Corp", {})
    assert res["is_verified"] is True
    assert res["status"] == "verified"
    assert "PROOF-SHA256" in res["audit_hash"]

def test_verifier_task_2_mark_paid():
    verifier = IndependentVerifier()
    # Seed bill INV-INI-001 is initially 'Approved', not 'Paid'
    res = verifier.verify_outcome("Mark the bill for invoice INV-INI-001 as paid.", {})
    assert res["is_verified"] is False

    # Mark as Paid in ledger
    conn = get_connection()
    conn.execute("UPDATE finance_bills SET status = 'Paid' WHERE invoice_number = 'INV-INI-001'")
    conn.commit()
    conn.close()

    res = verifier.verify_outcome("Mark the bill for invoice INV-INI-001 as paid.", {})
    assert res["is_verified"] is True
    assert res["status"] == "verified"

def test_verifier_task_4_ambiguity_clarification():
    verifier = IndependentVerifier()
    # If clarification was not asked, verification fails
    res_no_clarify = verifier.verify_outcome("Process the invoice from Acme", {"clarification_asked": False})
    assert res_no_clarify["is_verified"] is False

    # If clarification was properly asked, verification passes
    res_clarified = verifier.verify_outcome("Process the invoice from Acme", {"clarification_asked": True})
    assert res_clarified["is_verified"] is True
    assert res_clarified["status"] == "verified"
