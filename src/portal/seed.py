import os
import shutil
from datetime import datetime
from src.portal.db import get_connection, init_db, set_config

INVOICE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "invoices")

def generate_invoice_files():
    os.makedirs(INVOICE_DIR, exist_ok=True)

    # 1. Acme Corp Invoice 101 (Jan 2024)
    acme_101 = """<!DOCTYPE html>
<html>
<head>
    <title>Invoice INV-ACM-101</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 30px; color: #333; }
        .header { border-bottom: 2px solid #0284c7; padding-bottom: 10px; }
        .details { margin: 20px 0; }
        .amount-box { background: #f0f9ff; padding: 15px; border-radius: 8px; font-size: 1.2em; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #e2e8f0; padding: 10px; text-align: left; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Acme Corp</h1>
        <p>100 Enterprise Way, Suite 400, Austin, TX</p>
    </div>
    <div class="details">
        <p><strong>Invoice Number:</strong> INV-ACM-101</p>
        <p><strong>Invoice Date:</strong> 2024-01-15</p>
        <p><strong>Due Date:</strong> 2024-02-15</p>
        <p><strong>Customer:</strong> Enterprise Client</p>
    </div>
    <table>
        <tr><th>Description</th><th>Qty</th><th>Rate</th><th>Total</th></tr>
        <tr><td>Cloud Infrastructure - Q1 Base</td><td>1</td><td>$1,200.00</td><td>$1,200.00</td></tr>
    </table>
    <div class="amount-box">
        Total Due: $1,200.00
    </div>
</body>
</html>"""
    with open(os.path.join(INVOICE_DIR, "acme_invoice_101.html"), "w", encoding="utf-8") as f:
        f.write(acme_101)

    # 2. Acme Corp Invoice 102 (Mar 2024)
    acme_102 = """<!DOCTYPE html>
<html>
<head>
    <title>Invoice INV-ACM-102</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 30px; color: #333; }
        .header { border-bottom: 2px solid #0284c7; padding-bottom: 10px; }
        .details { margin: 20px 0; }
        .amount-box { background: #f0f9ff; padding: 15px; border-radius: 8px; font-size: 1.2em; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #e2e8f0; padding: 10px; text-align: left; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Acme Corp</h1>
        <p>100 Enterprise Way, Suite 400, Austin, TX</p>
    </div>
    <div class="details">
        <p><strong>Invoice Number:</strong> INV-ACM-102</p>
        <p><strong>Invoice Date:</strong> 2024-03-20</p>
        <p><strong>Due Date:</strong> 2024-04-20</p>
        <p><strong>Customer:</strong> Enterprise Client</p>
    </div>
    <table>
        <tr><th>Description</th><th>Qty</th><th>Rate</th><th>Total</th></tr>
        <tr><td>Cloud Scale Expansion Pack</td><td>1</td><td>$4,500.00</td><td>$4,500.00</td></tr>
    </table>
    <div class="amount-box">
        Total Due: $4,500.00
    </div>
</body>
</html>"""
    with open(os.path.join(INVOICE_DIR, "acme_invoice_102.html"), "w", encoding="utf-8") as f:
        f.write(acme_102)

    # 3. Acme Corp Invoice 103 (May 2024) - LATEST ACME INVOICE
    acme_103 = """<!DOCTYPE html>
<html>
<head>
    <title>Invoice INV-ACM-103</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 30px; color: #333; }
        .header { border-bottom: 2px solid #0284c7; padding-bottom: 10px; }
        .details { margin: 20px 0; }
        .amount-box { background: #ecfdf5; border: 1px solid #10b981; padding: 15px; border-radius: 8px; font-size: 1.2em; font-weight: bold; color: #065f46; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #e2e8f0; padding: 10px; text-align: left; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Acme Corp</h1>
        <p>100 Enterprise Way, Suite 400, Austin, TX</p>
    </div>
    <div class="details">
        <p><strong>Invoice Number:</strong> INV-ACM-103</p>
        <p><strong>Invoice Date:</strong> 2024-05-10</p>
        <p><strong>Due Date:</strong> 2024-06-10</p>
        <p><strong>Customer:</strong> Enterprise Client</p>
        <p><strong>Status:</strong> Unpaid / Final Notice</p>
    </div>
    <table>
        <tr><th>Description</th><th>Qty</th><th>Rate</th><th>Total</th></tr>
        <tr><td>Dedicated GPU Cluster - May billing</td><td>1</td><td>$8,250.00</td><td>$8,250.00</td></tr>
    </table>
    <div class="amount-box">
        Total Payable: $8,250.00
    </div>
    <p style="margin-top:20px; font-size: 0.9em; color:#64748b;">Wire routing: 021000021 | Acct: 884920412</p>
</body>
</html>"""
    with open(os.path.join(INVOICE_DIR, "acme_invoice_103_latest.html"), "w", encoding="utf-8") as f:
        f.write(acme_103)

    # 4. Cyberdyne Systems Messy Invoice (Text format, non-standard date, currency symbols and commas)
    cyberdyne_messy = """============================================================
CYBERDYNE SYSTEMS INCORPORATED
DEFENSE & AUTOMATION DIVISION
============================================================
Billing Statement & Commercial Invoice
Ref Code: CD-9042-X
Date Issued: 12th November 2024
Payment Terms: Net 30 Days
Due Date: December 12, 2024

Client: Enterprise FinOps Operations

STATEMENT SUMMARY:
------------------------------------------------------------
Item 1: Neural Network Coprocessor Cluster (Q4 Maintenance)
Quantity: 1
Unit Cost: $14,500.00 USD
Tax / Surcharge: Included

TOTAL AMOUNT DUE: $14,500.00 USD
(Fourteen Thousand Five Hundred US Dollars)

REMITTANCE NOTES:
Please remit within standard payment window. Invoices over
$10,000 require manual sign-off from VP Finance.
Bank Wire: CYBER-FED-990-2184
============================================================"""
    with open(os.path.join(INVOICE_DIR, "cyberdyne_messy_inv.txt"), "w", encoding="utf-8") as f:
        f.write(cyberdyne_messy)

    # 5. Globex Corp Invoice
    globex = """<!DOCTYPE html>
<html>
<head>
    <title>Invoice INV-GLO-501</title>
</head>
<body style="font-family: sans-serif; padding: 25px;">
    <h2>Globex Corporation</h2>
    <p>Invoice #: <strong>INV-GLO-501</strong></p>
    <p>Date: 2024-04-05</p>
    <p>Due Date: <strong>2024-05-05</strong></p>
    <p>Description: Security Audit & Compliance Monitoring</p>
    <h3>Amount: $3,400.00</h3>
</body>
</html>"""
    with open(os.path.join(INVOICE_DIR, "globex_invoice_501.html"), "w", encoding="utf-8") as f:
        f.write(globex)

def seed_database():
    init_db()
    generate_invoice_files()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Clear existing inbox and bills
    cursor.execute("DELETE FROM inbox_emails")
    cursor.execute("DELETE FROM finance_bills")
    cursor.execute("DELETE FROM failure_configs")
    try:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('inbox_emails', 'finance_bills')")
    except Exception:
        pass
    
    # Seed Emails
    emails = [
        (
            "Acme Corp",
            "billing@acme.com",
            "Invoice INV-ACM-101 for Cloud Base (Jan 2024)",
            "2024-01-16 09:15:00",
            "Hello Finance Team,\n\nPlease find attached invoice INV-ACM-101 for January cloud base services ($1,200.00). Due by 2024-02-15.\n\nBest regards,\nAcme Billing",
            "acme_invoice_101.html",
            os.path.join(INVOICE_DIR, "acme_invoice_101.html"),
            "INV-ACM-101",
            "2024-01-15",
            "2024-02-15",
            "2024-02-15",
            1200.00,
            "$1,200.00",
            0,
            1
        ),
        (
            "Acme Corp",
            "billing@acme.com",
            "Invoice INV-ACM-102 for Scale Expansion (Mar 2024)",
            "2024-03-21 11:30:00",
            "Hi,\n\nAttached is invoice INV-ACM-102 for March expansion services ($4,500.00). Due by 2024-04-20.\n\nThanks,\nAcme Billing Team",
            "acme_invoice_102.html",
            os.path.join(INVOICE_DIR, "acme_invoice_102.html"),
            "INV-ACM-102",
            "2024-03-20",
            "2024-04-20",
            "2024-04-20",
            4500.00,
            "$4,500.00",
            0,
            1
        ),
        (
            "Acme Corp",
            "billing@acme.com",
            "URGENT: Latest May Invoice INV-ACM-103 (GPU Dedicated Cluster)",
            "2024-05-11 14:02:00",
            "Dear Finance,\n\nAttached is our latest invoice INV-ACM-103 covering May dedicated cluster usage ($8,250.00). Due date is 2024-06-10.\nPlease process at your earliest convenience.\n\nSincerely,\nAcme Corp Accounts Receivable",
            "acme_invoice_103_latest.html",
            os.path.join(INVOICE_DIR, "acme_invoice_103_latest.html"),
            "INV-ACM-103",
            "2024-05-10",
            "2024-06-10",
            "2024-06-10",
            8250.00,
            "$8,250.00",
            0,
            0
        ),
        (
            "Cyberdyne Systems",
            "ar@cyberdyne.io",
            "Commercial Invoice CD-9042-X — Q4 AI Coprocessor Systems",
            "2024-11-13 16:45:00",
            "Attention Accounts Payable,\n\nAttached is statement CD-9042-X for $14,500.00 USD. Date of issue is 12th November 2024, payable on or before December 12, 2024.\nNote: High-value transaction requires approval.\n\nRegards,\nCyberdyne Systems Finance",
            "cyberdyne_messy_inv.txt",
            os.path.join(INVOICE_DIR, "cyberdyne_messy_inv.txt"),
            "CD-9042-X",
            "2024-11-12",
            "2024-12-12",
            "December 12, 2024",
            14500.00,
            "$14,500.00 USD",
            1,
            0
        ),
        (
            "Globex Corp",
            "accounts@globex.com",
            "Globex Security Monitoring Invoice INV-GLO-501",
            "2024-04-06 10:00:00",
            "Please find invoice INV-GLO-501 for April monitoring ($3,400.00). Due on 2024-05-05.\n\nThank you,\nGlobex Accounting",
            "globex_invoice_501.html",
            os.path.join(INVOICE_DIR, "globex_invoice_501.html"),
            "INV-GLO-501",
            "2024-04-05",
            "2024-05-05",
            "2024-05-05",
            3400.00,
            "$3,400.00",
            0,
            0
        )
    ]

    cursor.executemany("""
    INSERT INTO inbox_emails (
        vendor, sender, subject, received_date, body, attachment_name,
        attachment_path, invoice_number, invoice_date, invoice_due_date,
        raw_due_date, invoice_amount, raw_amount, is_messy, is_read
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, emails)

    # Seed 1 pre-existing bill from Initech to test bills list and duplicate detection
    cursor.execute("""
    INSERT INTO finance_bills (
        vendor, invoice_number, amount, due_date, notes, status, created_at
    ) VALUES (
        'Initech LLC',
        'INV-INI-001',
        800.00,
        '2024-03-31',
        'Initial office supplies retainer',
        'Approved',
        '2024-03-01 10:00:00'
    )
    """)

    # Default failure injection flags
    cursor.execute("INSERT INTO failure_configs (key, value) VALUES ('fail_500_count', '0')")
    cursor.execute("INSERT INTO failure_configs (key, value) VALUES ('slow_seconds', '0')")
    cursor.execute("INSERT INTO failure_configs (key, value) VALUES ('alt_layout', '0')")
    cursor.execute("INSERT INTO failure_configs (key, value) VALUES ('validation_error_count', '0')")

    conn.commit()
    conn.close()
    print("Seed data initialized successfully.")

if __name__ == "__main__":
    seed_database()
