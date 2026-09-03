"""
app/database.py - SQLite database layer (Module 14: Database Deployment)

Extended in the end-to-end pipeline update to include:
    - doc_results table  : per-document pipeline output (extraction,
                           classification, metrics, ratios, summary,
                           insights, anomalies). This is the sole
                           source of truth for newly uploaded documents
                           — no processed_data file-reading required.
    - documents table    : catalog (original Module 3 CSV mirror)
    - qa_log table       : Q&A interaction log
    - request_log table  : API monitoring log
"""

import os
import json
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
    # ── Pipeline results table (added for end-to-end processing) ────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS doc_results (
            document_id       TEXT PRIMARY KEY,
            filename          TEXT,
            status            TEXT,
            error             TEXT,
            word_count        INTEGER,
            num_pages         INTEGER,
            extraction_method TEXT,
            ocr_used          INTEGER,
            doc_category      TEXT,
            clf_confidence    REAL,
            clf_model         TEXT,
            doc_year          TEXT,
            metrics_json      TEXT,
            raw_values_json   TEXT,
            ratios_json       TEXT,
            financial_health  TEXT,
            summary_json      TEXT,
            insights_json     TEXT,
            anomalies_json    TEXT,
            processed_at      TEXT,
            user_id           INTEGER
        )
    """)
    # Add clf_model and clf_probs_json columns if they don't exist yet (backward compat)
    try:
        conn.execute("ALTER TABLE doc_results ADD COLUMN clf_model TEXT")
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE doc_results ADD COLUMN clf_probs_json TEXT")
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE doc_results ADD COLUMN user_id INTEGER")
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE documents ADD COLUMN user_id INTEGER")
        conn.commit()
    except Exception:
        pass

    # ── Users & Authentication Tables ─────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name     TEXT NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL,
            is_active     INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT NOT NULL,
            token      TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            used       INTEGER DEFAULT 0
        )
    """)
    conn.commit()

    # Seed default demo user and preserve existing documents
    demo_user = conn.execute("SELECT id FROM users WHERE email = 'demo@ledger.ai'").fetchone()
    if not demo_user:
        demo_hash = "$argon2id$v=19$m=65536,t=3,p=4$YgSC2WXDienoK02FiWFGQQ$74tnNeko0ILFtbRUWL55AbeV5xWur76oiI/m+/WmPNE"
        now_str = datetime.now().isoformat()
        cursor = conn.execute(
            "INSERT INTO users (full_name, email, password_hash, created_at, updated_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            ("Demo Analyst", "demo@ledger.ai", demo_hash, now_str, now_str)
        )
        demo_id = cursor.lastrowid
        conn.commit()
    else:
        demo_id = demo_user["id"]

    if demo_id:
        conn.execute("UPDATE doc_results SET user_id = ? WHERE user_id IS NULL", (demo_id,))
        conn.execute("UPDATE documents SET user_id = ? WHERE user_id IS NULL", (demo_id,))
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


# ═══════════════════════════════════════════════════════════════════════
# User & Authentication helpers
# ═══════════════════════════════════════════════════════════════════════
def create_user(full_name: str, email: str, password_hash: str) -> dict:
    """Create a new user. Raises ValueError if email already exists."""
    init_db()
    conn = get_connection()
    clean_email = email.strip().lower()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (clean_email,)).fetchone()
    if existing:
        conn.close()
        raise ValueError("An account with this email already exists.")

    now_str = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO users (full_name, email, password_hash, created_at, updated_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
        (full_name.strip(), clean_email, password_hash, now_str, now_str)
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": user_id, "full_name": full_name.strip(), "email": clean_email, "is_active": 1}


def get_user_by_email(email: str) -> dict | None:
    """Fetch user by email (case-insensitive)."""
    init_db()
    conn = get_connection()
    row = conn.execute(
        "SELECT id, full_name, email, password_hash, created_at, updated_at, is_active FROM users WHERE email = ?",
        (email.strip().lower(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    """Fetch user by integer ID."""
    init_db()
    conn = get_connection()
    row = conn.execute(
        "SELECT id, full_name, email, password_hash, created_at, updated_at, is_active FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_password(user_id: int, new_password_hash: str) -> bool:
    """Update a user's password hash."""
    init_db()
    conn = get_connection()
    now_str = datetime.now().isoformat()
    cursor = conn.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
        (new_password_hash, now_str, user_id)
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def create_password_reset(email: str, token: str, expires_at: str):
    """Store a password reset token."""
    init_db()
    conn = get_connection()
    conn.execute(
        "INSERT INTO password_resets (email, token, expires_at, used) VALUES (?, ?, ?, 0)",
        (email.strip().lower(), token, expires_at)
    )
    conn.commit()
    conn.close()


def get_password_reset(token: str) -> dict | None:
    """Get password reset record by token."""
    init_db()
    conn = get_connection()
    row = conn.execute(
        "SELECT id, email, token, expires_at, used FROM password_resets WHERE token = ?",
        (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_password_reset_used(token: str) -> bool:
    """Mark a password reset token as used."""
    init_db()
    conn = get_connection()
    cursor = conn.execute("UPDATE password_resets SET used = 1 WHERE token = ?", (token,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


# ═══════════════════════════════════════════════════════════════════════
# doc_results helpers — pipeline output per document (with user ownership)
# ═══════════════════════════════════════════════════════════════════════
def save_doc_result(doc_id: str, result: dict, user_id: int | None = None):
    """Upsert a pipeline result dict into doc_results with user_id."""
    init_db()
    extraction   = result.get("extraction") or {}
    clf          = result.get("classification") or {}
    metric_data  = result.get("metrics") or {}
    ratios       = result.get("ratios") or {}
    summary      = result.get("summary") or {}
    insights     = result.get("insights") or {}
    anomalies    = result.get("anomalies") or []

    # Strip internal _key numeric values (not for DB) from ratios
    clean_ratios = {k: v for k, v in ratios.items() if not k.startswith("_")}

    conn = get_connection()

    # Determine user_id to preserve or set
    if user_id is None:
        user_id = result.get("user_id")
    if user_id is None:
        existing = conn.execute("SELECT user_id FROM doc_results WHERE document_id = ?", (doc_id,)).fetchone()
        if existing and existing["user_id"] is not None:
            user_id = existing["user_id"]

    conn.execute("""
        INSERT OR REPLACE INTO doc_results
        (document_id, filename, status, error, word_count, num_pages,
         extraction_method, ocr_used, doc_category, clf_confidence, clf_model, clf_probs_json, doc_year,
         metrics_json, raw_values_json, ratios_json, financial_health,
         summary_json, insights_json, anomalies_json, processed_at, user_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        doc_id,
        result.get("filename", ""),
        result.get("status", "unknown"),
        result.get("error"),
        extraction.get("word_count"),
        extraction.get("num_pages"),
        extraction.get("extraction_method"),
        1 if extraction.get("ocr_used") else 0,
        clf.get("category"),
        clf.get("confidence"),
        clf.get("model_used"),
        json.dumps(clf.get("class_probabilities") or {}),
        metric_data.get("document_year"),
        json.dumps(metric_data.get("metrics", [])),
        json.dumps(metric_data.get("raw_values", {})),
        json.dumps(clean_ratios),
        clean_ratios.get("financial_health"),
        json.dumps(summary),
        json.dumps(insights),
        json.dumps(anomalies),
        result.get("processed_at", datetime.now().isoformat()),
        user_id,
    ))
    conn.commit()
    conn.close()


def get_doc_result(doc_id: str, user_id: int | None = None) -> dict | None:
    """Fetch a single pipeline result by document_id with optional user_id check."""
    init_db()
    conn = get_connection()
    if user_id is not None:
        row = conn.execute(
            "SELECT * FROM doc_results WHERE document_id = ? AND user_id = ?", (doc_id, user_id)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM doc_results WHERE document_id = ?", (doc_id,)
        ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    for key in ("metrics_json", "raw_values_json", "ratios_json",
                "summary_json", "insights_json", "anomalies_json", "clf_probs_json"):
        if d.get(key):
            try:
                dest_key = "class_probabilities" if key == "clf_probs_json" else key.replace("_json", "")
                d[dest_key] = json.loads(d[key])
            except Exception:
                pass
    return d


def get_all_doc_results(user_id: int | None = None) -> list:
    """Return pipeline results filtered by user_id if provided."""
    init_db()
    conn = get_connection()
    if user_id is not None:
        rows = conn.execute(
            "SELECT document_id, filename, status, doc_category, financial_health, "
            "word_count, num_pages, processed_at, error, user_id "
            "FROM doc_results WHERE user_id = ? ORDER BY processed_at DESC", (user_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT document_id, filename, status, doc_category, financial_health, "
            "word_count, num_pages, processed_at, error, user_id "
            "FROM doc_results ORDER BY processed_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_doc_result(doc_id: str, user_id: int | None = None) -> bool:
    """Delete a pipeline result by document_id ensuring user ownership."""
    init_db()
    conn = get_connection()
    if user_id is not None:
        cursor = conn.execute(
            "DELETE FROM doc_results WHERE document_id = ? AND user_id = ?", (doc_id, user_id)
        )
    else:
        cursor = conn.execute(
            "DELETE FROM doc_results WHERE document_id = ?", (doc_id,)
        )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


if __name__ == "__main__":
    catalog_path = os.path.join(BASE_DIR, "data", "raw", "dataset_catalog.csv")
    n = migrate_catalog_from_csv(catalog_path)
    print(f"[Module 14] Migrated {n} documents from CSV into SQLite: {DB_PATH}")
    docs = get_documents()
    print(f"[Module 14] Verified: {len(docs)} rows readable from the documents table.")
    print(f"[Module 14] Sample row: {docs[0]}")
