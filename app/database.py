"""
app/database.py - SQLite database layer (Module 14: Database Deployment)

The project has used flat CSV/JSON files through Modules 3-13, which
is fine for a single-user prototype. Module 14 asks for "Database
deployment" - this file provides a genuine, working relational
database (SQLite, built into Python's standard library - no server,
no internet, no extra install required) as the deployable data layer:

    - documents table   : mirrors data/raw/dataset_catalog.csv
    - qa_log table       : records every question asked through the
                            Q&A API/dashboard (also serves Module 14's
                            "Application monitoring" requirement - a
                            real usage log, not just a design note)

For a larger production deployment, this SQLite file would be swapped
for a managed database (AWS RDS / Azure SQL / Cloud SQL) - the
swap only touches this file; core.py's callers wouldn't change,
since they'd still just call get_documents() / log_qa_interaction().
"""

import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "app.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            document_type TEXT,
            scanned_copy TEXT,
            file_type TEXT,
            pages_or_rows TEXT,
            size_kb REAL,
            source TEXT,
            collected_on TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qa_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT,
            source_document TEXT,
            asked_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS request_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL,
            status TEXT NOT NULL,
            duration_ms REAL,
            requested_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def migrate_catalog_from_csv(catalog_csv_path: str):
    """One-time migration: load Module 3's CSV catalog into the
    documents table (idempotent - safe to run more than once)."""
    import csv
    init_db()
    conn = get_connection()
    with open(catalog_csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    for row in rows:
        conn.execute("""
            INSERT OR REPLACE INTO documents
            (document_id, filename, document_type, scanned_copy, file_type,
             pages_or_rows, size_kb, source, collected_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row.get("document_id"), row.get("filename"), row.get("document_type"),
            row.get("scanned_copy"), row.get("file_type"), row.get("pages_or_rows"),
            float(row["size_kb"]) if row.get("size_kb") else None,
            row.get("source"), row.get("collected_on"),
        ))
    conn.commit()
    conn.close()
    return len(rows)


def get_documents() -> list:
    init_db()
    conn = get_connection()
    rows = conn.execute("SELECT * FROM documents").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_qa_interaction(question: str, answer: str, source_document: str):
    """Application monitoring: persist every Q&A interaction."""
    init_db()
    conn = get_connection()
    conn.execute(
        "INSERT INTO qa_log (question, answer, source_document, asked_at) VALUES (?, ?, ?, ?)",
        (question, answer, source_document, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def log_request(endpoint: str, status: str, duration_ms: float):
    """Application monitoring: persist every API request (endpoint,
    status, response time) for later inspection / dashboarding."""
    init_db()
    conn = get_connection()
    conn.execute(
        "INSERT INTO request_log (endpoint, status, duration_ms, requested_at) VALUES (?, ?, ?, ?)",
        (endpoint, status, duration_ms, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_monitoring_summary() -> dict:
    """Basic monitoring dashboard data: request counts, error rate,
    average latency, and the most recent Q&A activity."""
    init_db()
    conn = get_connection()
    total_requests = conn.execute("SELECT COUNT(*) AS c FROM request_log").fetchone()["c"]
    error_requests = conn.execute(
        "SELECT COUNT(*) AS c FROM request_log WHERE status != '200'"
    ).fetchone()["c"]
    avg_latency = conn.execute(
        "SELECT AVG(duration_ms) AS a FROM request_log"
    ).fetchone()["a"]
    recent_qa = conn.execute(
        "SELECT question, answer, source_document, asked_at FROM qa_log "
        "ORDER BY id DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return {
        "total_requests": total_requests,
        "error_requests": error_requests,
        "error_rate_pct": round(error_requests / total_requests * 100, 1) if total_requests else 0,
        "avg_latency_ms": round(avg_latency, 2) if avg_latency else None,
        "recent_qa": [dict(r) for r in recent_qa],
    }


if __name__ == "__main__":
    catalog_path = os.path.join(BASE_DIR, "data", "raw", "dataset_catalog.csv")
    n = migrate_catalog_from_csv(catalog_path)
    print(f"[Module 14] Migrated {n} documents from CSV into SQLite: {DB_PATH}")
    docs = get_documents()
    print(f"[Module 14] Verified: {len(docs)} rows readable from the documents table.")
    print(f"[Module 14] Sample row: {docs[0]}")
