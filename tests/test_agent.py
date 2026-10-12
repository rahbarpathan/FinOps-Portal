import pytest
import asyncio
from src.portal.seed import seed_database
from src.agent.core import AutonomousAgent
from src.agent.verifier import IndependentVerifier
from src.agent.memory import WorkingMemory

@pytest.fixture(autouse=True)
def setup_environment():
    seed_database()

def test_working_memory():
    mem = WorkingMemory()
    mem.record_fact("vendor", "Acme Corp")
    mem.record_fact("amount", "8250.00")
    assert mem.get_fact("vendor") == "Acme Corp"
    assert mem.get_all_facts()["amount"] == "8250.00"

def test_independent_verifier_rejection_when_no_bill():
    verifier = IndependentVerifier()
    res = verifier.verify_task_outcome("Find invoice for Acme Corp", {})
    assert res["is_verified"] is False
    assert "No bill recorded" in res["summary"]

def test_independent_verifier_detects_older_vs_latest_invoice():
    # If a bill is manually inserted with an OLD invoice (e.g. INV-ACM-101 instead of latest INV-ACM-103)
    from src.portal.db import get_connection
    conn = get_connection()
    conn.execute("""
    INSERT INTO finance_bills (vendor, invoice_number, amount, due_date, notes, status, created_at)
    VALUES ('Acme Corp', 'INV-ACM-101', 1200.00, '2024-02-15', 'Old bill test', 'Pending', '2024-01-16')
    """)
    conn.commit()
    conn.close()

    verifier = IndependentVerifier()
    res = verifier.verify_task_outcome("Find the latest invoice from Acme Corp", {})
    # Check 2 (LATEST invoice check) should fail because INV-ACM-101 is not the latest (INV-ACM-103 is)!
    assert res["is_verified"] is False
    latest_check = next(c for c in res["checks"] if "LATEST invoice" in c["criterion"])
    assert latest_check["passed"] is False

def test_independent_verifier_passes_on_correct_latest_bill():
    from src.portal.db import get_connection
    conn = get_connection()
    conn.execute("""
    INSERT INTO finance_bills (vendor, invoice_number, amount, due_date, notes, status, created_at)
    VALUES ('Acme Corp', 'INV-ACM-103', 8250.00, '2024-06-10', 'Latest bill test', 'Pending', '2024-05-11')
    """)
    conn.commit()
    conn.close()

    verifier = IndependentVerifier()
    res = verifier.verify_task_outcome("Find the latest invoice from Acme Corp", {})
    assert res["is_verified"] is True
    assert all(c["passed"] for c in res["checks"])
    assert "PROOF-SHA256" in res["audit_hash"]
