import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List
from src.portal.db import get_connection

class IndependentVerifier:
    """
    Independent outcome verification engine.
    STRICTLY ISOLATED: Only accesses ground-truth state, never shared with the acting loop.
    """
    def __init__(self, ground_truth_url: str = "http://localhost:8000/api/ground-truth"):
        self.ground_truth_url = ground_truth_url

    def verify_task_outcome(self, task: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        task_lower = task.lower()
        target_vendor = "Acme Corp"
        if "cyberdyne" in task_lower:
            target_vendor = "Cyberdyne Systems"
        elif "globex" in task_lower:
            target_vendor = "Globex Corp"
        elif "initech" in task_lower:
            target_vendor = "Initech LLC"

        # Query isolated ground truth directly from database
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get bills for this vendor
        bills = cursor.execute(
            "SELECT * FROM finance_bills WHERE LOWER(vendor) LIKE ? ORDER BY id DESC",
            (f"%{target_vendor.lower()}%",)
        ).fetchall()
        
        # Get all inbox invoices for this vendor to verify "latest"
        inbox_invoices = cursor.execute(
            "SELECT invoice_number, invoice_date, invoice_due_date, invoice_amount FROM inbox_emails WHERE LOWER(vendor) LIKE ? ORDER BY invoice_date DESC",
            (f"%{target_vendor.lower()}%",)
        ).fetchall()
        conn.close()

        checks = []
        is_verified = True

        # Check 1: Bill exists in ledger
        has_bill = len(bills) > 0
        checks.append({
            "criterion": f"Bill registered in Internal Finance System for '{target_vendor}'",
            "passed": has_bill,
            "expected": f"At least 1 recorded bill for {target_vendor}",
            "actual": f"{len(bills)} bill(s) found in ledger"
        })
        if not has_bill:
            is_verified = False
            return {
                "is_verified": False,
                "summary": f"Verification failed: No bill recorded for vendor '{target_vendor}'.",
                "checks": checks,
                "audit_hash": "AUDIT_REJECTED_NO_RECORD",
                "timestamp": datetime.now().isoformat()
            }

        latest_created_bill = dict(bills[0])

        # Check 2: Latest invoice selected (date comparison)
        if inbox_invoices:
            expected_latest_inv = inbox_invoices[0]["invoice_number"]
            actual_inv = latest_created_bill["invoice_number"]
            passed_latest = (actual_inv.strip() == expected_latest_inv.strip())
            checks.append({
                "criterion": f"Selected LATEST invoice among all supplier correspondence (Date Comparison Check)",
                "passed": passed_latest,
                "expected": f"Latest Invoice Number: {expected_latest_inv} (dated {inbox_invoices[0]['invoice_date']})",
                "actual": f"Created Invoice Number: {actual_inv}"
            })
            if not passed_latest:
                is_verified = False

        # Check 3: Amount matches ground truth
        if inbox_invoices:
            expected_amount = float(inbox_invoices[0]["invoice_amount"])
            actual_amount = float(latest_created_bill["amount"])
            passed_amt = abs(expected_amount - actual_amount) < 0.01
            checks.append({
                "criterion": "Payable amount matches ground-truth invoice amount exactly",
                "passed": passed_amt,
                "expected": f"${expected_amount:,.2f}",
                "actual": f"${actual_amount:,.2f}"
            })
            if not passed_amt:
                is_verified = False

        # Check 4: Due date is valid YYYY-MM-DD
        due_date_val = str(latest_created_bill["due_date"]).strip()
        import re
        passed_date = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", due_date_val))
        checks.append({
            "criterion": "Due date formatted in strict ISO format (YYYY-MM-DD)",
            "passed": passed_date,
            "expected": "YYYY-MM-DD (e.g. 2024-06-10)",
            "actual": due_date_val
        })
        if not passed_date:
            is_verified = False

        # Check 5: Duplicate prevention
        inv_matches = [b for b in bills if b["invoice_number"] == latest_created_bill["invoice_number"]]
        passed_dup = (len(inv_matches) == 1)
        checks.append({
            "criterion": "Zero duplicate entries in general ledger",
            "passed": passed_dup,
            "expected": "Exactly 1 instance of invoice in finance system",
            "actual": f"{len(inv_matches)} instance(s) found"
        })
        if not passed_dup:
            is_verified = False

        # Cryptographic Audit Hash for proof
        audit_raw = f"{target_vendor}|{latest_created_bill['invoice_number']}|{latest_created_bill['amount']}|{datetime.now().strftime('%Y%m%d%H')}"
        audit_hash = hashlib.sha256(audit_raw.encode()).hexdigest()[:16].upper()

        summary = (
            f"Independent verification PASSED: Bill #{latest_created_bill['id']} for '{target_vendor}' "
            f"({latest_created_bill['invoice_number']}) verified with amount ${latest_created_bill['amount']:,.2f} "
            f"due {latest_created_bill['due_date']}."
            if is_verified else
            "Independent verification FAILED: One or more audit checks did not match ground-truth state."
        )

        return {
            "is_verified": is_verified,
            "summary": summary,
            "checks": checks,
            "audit_hash": f"PROOF-SHA256-{audit_hash}",
            "screenshot_url": evidence.get("screenshot_url") if isinstance(evidence, dict) else None,
            "timestamp": datetime.now().isoformat(),
            "bill_id": latest_created_bill["id"]
        }
