import pytest
from fastapi.testclient import TestClient
from env.app import app
from env.seed import seed_database
from env.db import get_connection

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_environment():
    seed_database()

def test_inbox_emails_and_dates():
    res = client.get("/inbox")
    assert res.status_code == 200
    assert "Acme Corp" in res.text
    assert "Cyberdyne Systems" in res.text
    assert "Globex Corp" in res.text
    assert "INV-ACM-101" in res.text
    assert "INV-ACM-102" in res.text
    assert "INV-ACM-103" in res.text

def test_attachment_view():
    res = client.get("/inbox/attachment/3")
    assert res.status_code == 200
    assert "INV-ACM-103" in res.text
    assert "8,250.00" in res.text
    assert "2024-05-10" in res.text

def test_messy_invoice_attachment():
    res = client.get("/inbox/attachment/5")
    assert res.status_code == 200
    assert "CD-9042-X" in res.text
    assert "$14,500.00 USD" in res.text
    assert "Notice: This invoice contains non-standard text formatting" in res.text

def test_create_bill_validation_due_date():
    # Attempt submission with invalid date format (e.g. MM/DD/YYYY)
    payload = {
        "vendor": "Acme Corp",
        "invoice_number": "INV-TEST-001",
        "amount": "1000.00",
        "due_date": "12/31/2024",
        "notes": "Testing invalid date format"
    }
    res = client.post("/bills/create", data=payload)
    assert res.status_code == 400
    assert "Invalid due date format" in res.text

def test_create_bill_validation_amount():
    # Attempt submission with currency symbol
    payload = {
        "vendor": "Acme Corp",
        "invoice_number": "INV-TEST-002",
        "amount": "$1,000.00",
        "due_date": "2024-12-31",
        "notes": "Testing non-numeric amount"
    }
    res = client.post("/bills/create", data=payload)
    assert res.status_code == 400
    assert "Invalid amount format" in res.text

def test_create_bill_duplicate_rejection():
    # Attempt duplicate of seed bill INV-INI-001
    payload = {
        "vendor": "Initech LLC",
        "invoice_number": "INV-INI-001",
        "amount": "800.00",
        "due_date": "2024-03-31",
        "notes": "Duplicate test"
    }
    res = client.post("/bills/create", data=payload)
    assert res.status_code == 400
    assert "Duplicate Invoice" in res.text

def test_create_bill_success():
    payload = {
        "vendor": "Acme Corp",
        "invoice_number": "INV-ACM-103",
        "amount": "8250.00",
        "due_date": "2024-06-10",
        "notes": "Valid bill test"
    }
    res = client.post("/bills/create", data=payload, follow_redirects=True)
    assert res.status_code == 200
    assert "INV-ACM-103" in res.text
    assert "8250.00" in res.text

def test_ground_truth_isolation():
    res = client.get("/api/ground-truth")
    assert res.status_code == 200
    data = res.json()
    assert "bills" in data
    assert "emails" in data
    assert data["seed_signature"] == "CENTRALIGN_FINOPS_SEED_OK"
