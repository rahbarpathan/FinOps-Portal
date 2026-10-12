"""
Deterministic seed data generator and reset mechanism for FinOps Portal.
Provides emails, multiple invoices per vendor across dates, messy formatting,
pre-existing bills for status updates and 7-day filtering.
"""
import os
from datetime import datetime
from env.db import get_connection, init_db, set_config

INVOICE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "invoices")

def generate_invoice_files():
    os.makedirs(INVOICE_DIR, exist_ok=True)

    # 1. Acme Corp 101 (Jan 2024)
    with open(os.path.join(INVOICE_DIR, "acme_invoice_101.html"), "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html><html><head><title>Invoice INV-ACM-101</title></head>
<body style="font-family: Arial, sans-serif; padding: 25px;">
    <h2>Acme Corp</h2>
    <p><strong>Invoice Number:</strong> INV-ACM-101</p>
    <p><strong>Invoice Date:</strong> 2024-01-15</p>
    <p><strong>Due Date:</strong> 2024-02-15</p>
    <h3>Amount Due: $1,200.00</h3>
</body></html>""")

    # 2. Acme Corp 102 (Mar 2024)
    with open(os.path.join(INVOICE_DIR, "acme_invoice_102.html"), "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html><html><head><title>Invoice INV-ACM-102</title></head>
<body style="font-family: Arial, sans-serif; padding: 25px;">
    <h2>Acme Corp</h2>
    <p><strong>Invoice Number:</strong> INV-ACM-102</p>
    <p><strong>Invoice Date:</strong> 2024-03-20</p>
    <p><strong>Due Date:</strong> 2024-04-20</p>
    <h3>Amount Due: $4,500.00</h3>
</body></html>""")

    # 3. Acme Corp 103 (May 2024 - LATEST Acme Corp)
    with open(os.path.join(INVOICE_DIR, "acme_invoice_103_latest.html"), "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html><html><head><title>Invoice INV-ACM-103</title></head>
<body style="font-family: Arial, sans-serif; padding: 25px;">
    <h2>Acme Corp</h2>
    <p><strong>Invoice Number:</strong> INV-ACM-103</p>
    <p><strong>Invoice Date:</strong> 2024-05-10</p>
    <p><strong>Due Date:</strong> 2024-06-10</p>
    <p><strong>Service:</strong> Dedicated GPU Compute Cluster</p>
    <h3 style="color:#059669;">Total Amount Due: $8,250.00</h3>
</body></html>""")

    # 4. Acme Logistics 001 (Creates ambiguity for "Process the invoice from Acme")
    with open(os.path.join(INVOICE_DIR, "acme_logistics_001.html"), "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html><html><head><title>Invoice INV-LOG-001</title></head>
<body style="font-family: Arial, sans-serif; padding: 25px;">
    <h2>Acme Logistics Supply Chain</h2>
    <p><strong>Invoice Number:</strong> INV-LOG-001</p>
    <p><strong>Invoice Date:</strong> 2024-10-01</p>
    <p><strong>Due Date:</strong> 2024-11-01</p>
    <h3>Total Due: $1,900.00</h3>
</body></html>""")

    # 5. Cyberdyne Systems (Messy invoice)
    with open(os.path.join(INVOICE_DIR, "cyberdyne_messy_inv.txt"), "w", encoding="utf-8") as f:
        f.write("""============================================================
CYBERDYNE SYSTEMS INCORPORATED
Billing Statement & Commercial Invoice
Ref Code: CD-9042-X
Date Issued: 12th November 2024
Due Date: December 12, 2024

TOTAL AMOUNT DUE: $14,500.00 USD
(Fourteen Thousand Five Hundred US Dollars)
Payment Terms: Net 30. High-value transactions require VP sign-off.
============================================================""")

    # 6. Globex Corp
    with open(os.path.join(INVOICE_DIR, "globex_invoice_501.html"), "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html><html><head><title>Invoice INV-GLO-501</title></head>
<body style="font-family: Arial, sans-serif; padding: 25px;">
    <h2>Globex Corporation</h2>
    <p><strong>Invoice Number:</strong> INV-GLO-501</p>
    <p><strong>Invoice Date:</strong> 2024-04-05</p>
    <p><strong>Due Date:</strong> 2024-05-05</p>
    <h3>Amount: $3,400.00</h3>
</body></html>""")

def seed_database():
    init_db()
    generate_invoice_files()

    conn = get_connection()
    cursor = conn.cursor()

    # Reset tables and autoincrement sequence
    cursor.execute("DELETE FROM inbox_emails")
    cursor.execute("DELETE FROM finance_bills")
    cursor.execute("DELETE FROM failure_configs")
    try:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('inbox_emails', 'finance_bills')")
    except Exception:
        pass

    emails = [
        (
            "Acme Corp", "billing@acme.com", "Invoice INV-ACM-101 (Jan 2024)", "2024-01-16 09:15:00",
            "Attached invoice INV-ACM-101 for January ($1,200.00).",
            "acme_invoice_101.html", os.path.join(INVOICE_DIR, "acme_invoice_101.html"),
            "INV-ACM-101", "2024-01-15", "2024-02-15", "2024-02-15", 1200.00, "$1,200.00", 0, 1
        ),
        (
            "Acme Corp", "billing@acme.com", "Invoice INV-ACM-102 (Mar 2024)", "2024-03-21 11:30:00",
            "Attached invoice INV-ACM-102 for March ($4,500.00).",
            "acme_invoice_102.html", os.path.join(INVOICE_DIR, "acme_invoice_102.html"),
            "INV-ACM-102", "2024-03-20", "2024-04-20", "2024-04-20", 4500.00, "$4,500.00", 0, 1
        ),
        (
            "Acme Corp", "billing@acme.com", "URGENT: Latest May Invoice INV-ACM-103", "2024-05-11 14:02:00",
            "Attached is our latest invoice INV-ACM-103 ($8,250.00). Due 2024-06-10.",
            "acme_invoice_103_latest.html", os.path.join(INVOICE_DIR, "acme_invoice_103_latest.html"),
            "INV-ACM-103", "2024-05-10", "2024-06-10", "2024-06-10", 8250.00, "$8,250.00", 0, 0
        ),
        (
            "Acme Logistics", "dispatch@acmelogistics.com", "Freight Invoice INV-LOG-001", "2024-10-02 08:00:00",
            "Attached freight forwarding invoice INV-LOG-001 ($1,900.00).",
            "acme_logistics_001.html", os.path.join(INVOICE_DIR, "acme_logistics_001.html"),
            "INV-LOG-001", "2024-10-01", "2024-11-01", "2024-11-01", 1900.00, "$1,900.00", 0, 0
        ),
        (
            "Cyberdyne Systems", "ar@cyberdyne.io", "Commercial Statement CD-9042-X", "2024-11-13 16:45:00",
            "Attached statement CD-9042-X for $14,500.00 USD. Due December 12, 2024.",
            "cyberdyne_messy_inv.txt", os.path.join(INVOICE_DIR, "cyberdyne_messy_inv.txt"),
            "CD-9042-X", "2024-11-12", "2024-12-12", "December 12, 2024", 14500.00, "$14,500.00 USD", 1, 0
        ),
        (
            "Globex Corp", "accounts@globex.com", "Security Monitoring Invoice INV-GLO-501", "2024-04-06 10:00:00",
            "Attached invoice INV-GLO-501 ($3,400.00). Due 2024-05-05.",
            "globex_invoice_501.html", os.path.join(INVOICE_DIR, "globex_invoice_501.html"),
            "INV-GLO-501", "2024-04-05", "2024-05-05", "2024-05-05", 3400.00, "$3,400.00", 0, 0
        )
    ]

    cursor.executemany("""
    INSERT INTO inbox_emails (
        vendor, sender, subject, received_date, body, attachment_name,
        attachment_path, invoice_number, invoice_date, invoice_due_date,
        raw_due_date, invoice_amount, raw_amount, is_messy, is_read
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, emails)

    # Seed pre-existing bills in internal finance system
    # Current date anchor is 2026-10-12
    bills = [
        ("Initech LLC", "INV-INI-001", 800.00, "2026-10-15", "Office consulting retainer", "Approved", "2026-10-01 10:00:00"),
        ("Wayne Enterprises", "INV-WAY-002", 2100.00, "2026-10-17", "Defense R&D materials", "Pending", "2026-10-05 14:00:00"),
        ("Stark Industries", "INV-STK-003", 15000.00, "2026-11-20", "Energy grid monitoring", "Pending", "2026-10-02 11:00:00"),
        ("Oscorp Corp", "INV-OSC-004", 5400.00, "2026-09-01", "Biomedical hardware maintenance", "Paid", "2026-08-15 09:00:00")
    ]

    cursor.executemany("""
    INSERT INTO finance_bills (vendor, invoice_number, amount, due_date, notes, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, bills)

    # Reset failure injection defaults
    cursor.execute("INSERT INTO failure_configs (key, value) VALUES ('fail_500_count', '0')")
    cursor.execute("INSERT INTO failure_configs (key, value) VALUES ('slow_seconds', '0')")
    cursor.execute("INSERT INTO failure_configs (key, value) VALUES ('alt_layout', '0')")
    cursor.execute("INSERT INTO failure_configs (key, value) VALUES ('validation_error_count', '0')")

    conn.commit()
    conn.close()
    print("Deterministic seed data initialized successfully.")

if __name__ == "__main__":
    seed_database()
