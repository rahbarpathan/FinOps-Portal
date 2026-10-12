import pytest
from fastapi.testclient import TestClient
from env.app import app
from env.seed import seed_database
from env.db import set_config

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_environment():
    seed_database()

def test_failure_injection_500_recovery():
    # Configure 500 failure injection once
    client.post("/api/chaos", json={"action": "fail_500"})
    
    payload = {
        "vendor": "Acme Corp",
        "invoice_number": "INV-REC-500",
        "amount": "1200.00",
        "due_date": "2024-05-15",
        "notes": "Testing 500 error injection"
    }

    # First attempt should fail with 500
    res1 = client.post("/bills/create", data=payload)
    assert res1.status_code == 500
    assert "Injected Failure to verify Agent Retry Recovery" in res1.text

    # Second attempt (automatic retry) should succeed
    res2 = client.post("/bills/create", data=payload, follow_redirects=True)
    assert res2.status_code == 200
    assert "INV-REC-500" in res2.text

def test_failure_injection_validation_error_recovery():
    # Configure validation error injection once
    client.post("/api/chaos", json={"action": "validation_err"})

    payload = {
        "vendor": "Acme Corp",
        "invoice_number": "INV-REC-VAL",
        "amount": "2500.00",
        "due_date": "2024-05-20",
        "notes": "Initial attempt"
    }

    # First attempt should return 400 with injected error
    res1 = client.post("/bills/create", data=payload)
    assert res1.status_code == 400
    assert "Validation Error (First Attempt)" in res1.text

    # Second attempt after adapting notes should succeed
    payload["notes"] = "Vendor tax authorization code confirmed."
    res2 = client.post("/bills/create", data=payload, follow_redirects=True)
    assert res2.status_code == 200
    assert "INV-REC-VAL" in res2.text

def test_alt_layout_toggle():
    # Toggle alt layout
    client.post("/api/chaos", json={"action": "alt_layout"})
    res = client.get("/bills/create")
    assert res.status_code == 200
    assert "Submit Payment Voucher" in res.text
    assert "Alternative Layout Mode Active" in res.text
