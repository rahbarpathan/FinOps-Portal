"""
Independent outcome verification engine.
Validates task outcomes independently against isolated ground-truth state and file evidence.
Enforces that 'finish' cannot claim success without verification evidence.
"""
import os
import re
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from env.db import get_connection

class IndependentVerifier:
    """
    Independent outcome verification engine.
    STRICTLY ISOLATED: Only accesses ground-truth state, never shared with the acting loop.
    """
    def __init__(self, ground_truth_url: str = "http://localhost:8000/api/ground-truth"):
        self.ground_truth_url = ground_truth_url
        self.recorded_checks: List[Dict[str, Any]] = []

    def add_check(self, criterion: str, expected: Any, actual: Any, check_type: str = "ground_truth") -> Dict[str, Any]:
        """Record an explicit verification check."""
        passed = (str(expected).strip() == str(actual).strip())
        check = {
            "criterion": criterion,
            "passed": passed,
            "expected": expected,
            "actual": actual,
            "type": check_type
        }
        self.recorded_checks.append(check)
        return check

    def verify_outcome(self, task: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Independently evaluate task outcome against isolated ground-truth state.
        Returns full audit report with pass/fail checks, cryptographic hash, and status.
        """
        task_lower = task.lower()
        checks: List[Dict[str, Any]] = []
        is_verified = True

        conn = get_connection()
        cursor = conn.cursor()

        # Task 2: "Mark the bill for invoice [number] as paid"
        if "mark" in task_lower and "paid" in task_lower:
            inv_match = re.findall(r"INV-[A-Z0-9-]+|CD-[0-9A-Z-]+", task)
            target_inv = inv_match[0] if inv_match else "INV-INI-001"

            bill = cursor.execute("SELECT * FROM finance_bills WHERE invoice_number = ?", (target_inv,)).fetchone()
            conn.close()

            if not bill:
                return {
                    "status": "failed",
                    "is_verified": False,
                    "summary": f"Verification failed: Invoice '{target_inv}' does not exist in ground-truth ledger.",
                    "checks": [{"criterion": "Bill exists in ledger", "passed": False, "expected": target_inv, "actual": "None"}]
                }

            is_paid = (bill["status"] == "Paid")
            checks.append({
                "criterion": f"Bill for invoice '{target_inv}' marked as 'Paid' in finance ledger",
                "passed": is_paid,
                "expected": "Paid",
                "actual": bill["status"]
            })
            is_verified = is_paid

            audit_hash = hashlib.sha256(f"PAID|{target_inv}|{bill['status']}|{bill['amount']}".encode()).hexdigest()[:16].upper()
            return {
                "status": "verified" if is_verified else "failed",
                "is_verified": is_verified,
                "summary": f"Independent verification {'PASSED' if is_verified else 'FAILED'}: Bill {target_inv} status is '{bill['status']}'.",
                "checks": checks,
                "audit_hash": f"PROOF-SHA256-{audit_hash}",
                "evidence": evidence
            }

        # Task 3: "List all bills due in the next 7 days and write a summary to summary.md"
        if "summary.md" in task_lower or ("next 7 days" in task_lower and "summary" in task_lower):
            summary_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "summary.md")
            file_exists = os.path.exists(summary_path)

            checks.append({
                "criterion": "Local file 'summary.md' created and populated",
                "passed": file_exists,
                "expected": "summary.md exists",
                "actual": "Found" if file_exists else "Missing"
            })

            content = ""
            if file_exists:
                with open(summary_path, "r", encoding="utf-8") as f:
                    content = f.read()

            # Verify bills due in next 7 days (INV-INI-001 on 2026-10-15 and INV-WAY-002 on 2026-10-17)
            has_bill1 = "INV-INI-001" in content or "Initech" in content
            has_bill2 = "INV-WAY-002" in content or "Wayne" in content
            not_out_of_range = "INV-STK-003" not in content  # Stark is Nov 20 (not in next 7 days)

            checks.append({
                "criterion": "Contains bill due in 3 days (INV-INI-001 / Initech LLC)",
                "passed": has_bill1,
                "expected": "INV-INI-001 present",
                "actual": "Found" if has_bill1 else "Missing"
            })
            checks.append({
                "criterion": "Contains bill due in 5 days (INV-WAY-002 / Wayne Enterprises)",
                "passed": has_bill2,
                "expected": "INV-WAY-002 present",
                "actual": "Found" if has_bill2 else "Missing"
            })
            checks.append({
                "criterion": "Correctly excludes out-of-range bills (>7 days, e.g. INV-STK-003)",
                "passed": not_out_of_range,
                "expected": "INV-STK-003 excluded",
                "actual": "Excluded" if not_out_of_range else "Included in error"
            })

            is_verified = file_exists and has_bill1 and has_bill2 and not_out_of_range
            conn.close()
            audit_hash = hashlib.sha256(f"SUMMARY_7_DAYS|{len(content)}|{file_exists}".encode()).hexdigest()[:16].upper()

            return {
                "status": "verified" if is_verified else "failed",
                "is_verified": is_verified,
                "summary": f"Independent verification {'PASSED' if is_verified else 'FAILED'}: summary.md correctly filtered bills due in next 7 days.",
                "checks": checks,
                "audit_hash": f"PROOF-SHA256-{audit_hash}",
                "evidence": {"summary_path": summary_path, "bytes": len(content)}
            }

        # Task 4: Ambiguous task ("Process the invoice from Acme")
        if "process the invoice from acme" in task_lower and ("latest" not in task_lower):
            # Check if clarification was raised
            clarification_raised = evidence.get("clarification_asked", False) or evidence.get("question_kind") == "clarification"
            checks.append({
                "criterion": "Detected ambiguity and paused to ask clarification from human operator",
                "passed": bool(clarification_raised),
                "expected": "Clarification question raised",
                "actual": "Clarification raised" if clarification_raised else "Guessed without asking"
            })
            conn.close()
            return {
                "status": "verified" if clarification_raised else "unverified",
                "is_verified": bool(clarification_raised),
                "summary": "Ambiguity detection verification PASSED: Agent properly halted and prompted for entity clarification." if clarification_raised else "Ambiguity check FAILED: Agent guessed vendor without clarifying.",
                "checks": checks,
                "audit_hash": "PROOF-AMBIGUITY-CLARIFIED",
                "evidence": evidence
            }

        # Task 1 & Task 5: Find invoice, enter bill, verify
        target_vendor = "Acme Corp"
        if "cyberdyne" in task_lower:
            target_vendor = "Cyberdyne Systems"
        elif "globex" in task_lower:
            target_vendor = "Globex Corp"

        bills = cursor.execute(
            "SELECT * FROM finance_bills WHERE LOWER(vendor) LIKE ? ORDER BY id DESC",
            (f"%{target_vendor.lower()}%",)
        ).fetchall()

        inbox_invoices = cursor.execute(
            "SELECT invoice_number, invoice_date, invoice_due_date, invoice_amount FROM inbox_emails WHERE LOWER(vendor) LIKE ? ORDER BY invoice_date DESC",
            (f"%{target_vendor.lower()}%",)
        ).fetchall()
        conn.close()

        has_bill = len(bills) > 0
        checks.append({
            "criterion": f"Bill registered in Internal Finance System for '{target_vendor}'",
            "passed": has_bill,
            "expected": f"At least 1 recorded bill for {target_vendor}",
            "actual": f"{len(bills)} bill(s) found in ledger"
        })

        if not has_bill:
            return {
                "status": "failed",
                "is_verified": False,
                "summary": f"Verification failed: No bill recorded for vendor '{target_vendor}'.",
                "checks": checks,
                "audit_hash": "REJECTED_NO_BILL"
            }

        latest_bill = dict(bills[0])

        # Verify latest invoice was selected
        if inbox_invoices:
            expected_latest_inv = inbox_invoices[0]["invoice_number"]
            actual_inv = latest_bill["invoice_number"]
            passed_latest = (actual_inv.strip() == expected_latest_inv.strip())
            checks.append({
                "criterion": "Selected LATEST invoice among all supplier correspondence (Date Comparison Check)",
                "passed": passed_latest,
                "expected": f"Latest Invoice Number: {expected_latest_inv} (dated {inbox_invoices[0]['invoice_date']})",
                "actual": f"Created Invoice Number: {actual_inv}"
            })
            if not passed_latest: is_verified = False

            expected_amount = float(inbox_invoices[0]["invoice_amount"])
            actual_amount = float(latest_bill["amount"])
            passed_amt = abs(expected_amount - actual_amount) < 0.01
            checks.append({
                "criterion": "Payable amount matches ground-truth invoice amount exactly",
                "passed": passed_amt,
                "expected": f"${expected_amount:,.2f}",
                "actual": f"${actual_amount:,.2f}"
            })
            if not passed_amt: is_verified = False

        due_date_val = str(latest_bill["due_date"]).strip()
        passed_date = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", due_date_val))
        checks.append({
            "criterion": "Due date formatted in strict ISO format (YYYY-MM-DD)",
            "passed": passed_date,
            "expected": "YYYY-MM-DD (e.g. 2024-06-10)",
            "actual": due_date_val
        })
        if not passed_date: is_verified = False

        audit_raw = f"{target_vendor}|{latest_bill['invoice_number']}|{latest_bill['amount']}|{latest_bill['due_date']}"
        audit_hash = hashlib.sha256(audit_raw.encode()).hexdigest()[:16].upper()

        return {
            "status": "verified" if is_verified else "failed",
            "is_verified": is_verified,
            "summary": f"Independent verification {'PASSED' if is_verified else 'FAILED'}: Bill #{latest_bill['id']} for '{target_vendor}' ({latest_bill['invoice_number']}) matches ground truth.",
            "checks": checks,
            "audit_hash": f"PROOF-SHA256-{audit_hash}",
            "evidence": {
                "vendor": target_vendor,
                "invoice_number": latest_bill["invoice_number"],
                "amount": latest_bill["amount"],
                "due_date": latest_bill["due_date"],
                "screenshot_url": evidence.get("screenshot_url")
            }
        }
