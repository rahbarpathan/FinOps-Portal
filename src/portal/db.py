import os
import sqlite3
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "finops.db")

def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Inbox emails table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inbox_emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor TEXT NOT NULL,
        sender TEXT NOT NULL,
        subject TEXT NOT NULL,
        received_date TEXT NOT NULL,
        body TEXT NOT NULL,
        attachment_name TEXT NOT NULL,
        attachment_path TEXT NOT NULL,
        invoice_number TEXT NOT NULL,
        invoice_date TEXT NOT NULL,
        invoice_due_date TEXT NOT NULL,
        raw_due_date TEXT NOT NULL,
        invoice_amount REAL NOT NULL,
        raw_amount TEXT NOT NULL,
        is_messy INTEGER DEFAULT 0,
        is_read INTEGER DEFAULT 0
    )
    """)
    
    # Internal Finance System bills table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS finance_bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor TEXT NOT NULL,
        invoice_number TEXT NOT NULL UNIQUE,
        amount REAL NOT NULL,
        due_date TEXT NOT NULL,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'Pending',
        created_at TEXT NOT NULL
    )
    """)
    
    # Failure injection runtime state table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS failure_configs (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

def get_config(key: str, default: str = "") -> str:
    conn = get_connection()
    row = conn.execute("SELECT value FROM failure_configs WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def set_config(key: str, value: str):
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO failure_configs (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()
