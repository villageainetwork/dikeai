"""
DIKE AI — Database Foundation
SQLite storage for audit results, compliance scores, and certificates.
"""

import sqlite3
import os
import datetime
import uuid

DB_FILE = os.environ.get("DIKE_DB", "dike.db")


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    c = conn.cursor()

    # Audits table — stores every audit run
    c.execute("""
        CREATE TABLE IF NOT EXISTS audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id TEXT UNIQUE NOT NULL,
            org_name TEXT,
            org_email TEXT,
            audit_type TEXT DEFAULT 'guided',
            regulation TEXT DEFAULT 'DPDP Act 2023',
            answers_json TEXT,
            results_json TEXT,
            overall_score INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Scores table — sub-scores by category
    c.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id TEXT NOT NULL,
            category TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            max_score INTEGER DEFAULT 100,
            status TEXT DEFAULT 'needs_work',
            recommendation TEXT,
            FOREIGN KEY (audit_id) REFERENCES audits(audit_id)
        )
    """)

    # Certificates table — shareable compliance certificates
    c.execute("""
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cert_slug TEXT UNIQUE NOT NULL,
            audit_id TEXT NOT NULL,
            org_name TEXT NOT NULL,
            regulation TEXT DEFAULT 'DPDP Act 2023',
            overall_score INTEGER DEFAULT 0,
            status_label TEXT,
            issued_at TEXT DEFAULT CURRENT_TIMESTAMP,
            valid_until TEXT,
            is_public INTEGER DEFAULT 1,
            FOREIGN KEY (audit_id) REFERENCES audits(audit_id)
        )
    """)

    conn.commit()
    conn.close()


def save_audit(org_name, org_email, answers, results, scores_by_category, regulation="DPDP Act 2023"):
    """Save a completed audit and return the audit_id."""
    import json

    audit_id = str(uuid.uuid4())[:8].upper()
    overall_score = int(sum(scores_by_category.values()) / len(scores_by_category)) if scores_by_category else 0

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        INSERT INTO audits (audit_id, org_name, org_email, audit_type, regulation,
                           answers_json, results_json, overall_score, created_at)
        VALUES (?, ?, ?, 'guided', ?, ?, ?, ?, ?)
    """, (
        audit_id, org_name, org_email, regulation,
        json.dumps(answers), json.dumps(results),
        overall_score,
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    # Save category scores
    status_map = {
        range(0, 40): "critical",
        range(40, 60): "needs_work",
        range(60, 80): "moderate",
        range(80, 101): "good"
    }

    for category, score in scores_by_category.items():
        status = "needs_work"
        for r, s in status_map.items():
            if score in r:
                status = s
                break
        c.execute("""
            INSERT INTO scores (audit_id, category, score, max_score, status)
            VALUES (?, ?, ?, 100, ?)
        """, (audit_id, category, score, status))

    conn.commit()
    conn.close()
    return audit_id


def get_audit(audit_id):
    """Retrieve audit by ID."""
    import json
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT * FROM audits WHERE audit_id = ?", (audit_id,)).fetchone()
    scores = c.execute("SELECT * FROM scores WHERE audit_id = ?", (audit_id,)).fetchall()
    conn.close()
    if not row:
        return None, []
    audit = dict(row)
    audit["answers"] = json.loads(audit.get("answers_json") or "{}")
    audit["results"] = json.loads(audit.get("results_json") or "[]")
    return audit, [dict(s) for s in scores]


def save_certificate(audit_id, org_name, overall_score, regulation="DPDP Act 2023"):
    """Create a shareable certificate for an audit."""
    import re
    # Generate a clean slug from org name
    slug = re.sub(r'[^a-z0-9]+', '-', org_name.lower()).strip('-')
    slug = f"{slug}-{audit_id.lower()}"

    # Determine status label
    if overall_score >= 80:
        status_label = "Substantially Compliant"
    elif overall_score >= 60:
        status_label = "Partially Compliant"
    elif overall_score >= 40:
        status_label = "Moderate Risk"
    else:
        status_label = "High Risk — Action Required"

    issued = datetime.datetime.now()
    valid_until = (issued + datetime.timedelta(days=180)).strftime("%B %d, %Y")
    issued_str = issued.strftime("%B %d, %Y")

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO certificates (cert_slug, audit_id, org_name, regulation,
                                     overall_score, status_label, issued_at, valid_until)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (slug, audit_id, org_name, regulation, overall_score,
              status_label, issued_str, valid_until))
        conn.commit()
    except Exception:
        pass
    conn.close()
    return slug


def get_certificate(cert_slug):
    """Retrieve certificate by slug."""
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT * FROM certificates WHERE cert_slug = ?", (cert_slug,)).fetchone()
    conn.close()
    return dict(row) if row else None


# Initialise database on import
init_db()