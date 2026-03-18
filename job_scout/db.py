"""SQLite database for tracking seen jobs."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "job_scout.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                url TEXT NOT NULL,
                source TEXT NOT NULL,
                posted_at TEXT NOT NULL,
                first_seen TEXT NOT NULL
            )
        """)
        conn.commit()


def is_seen(job_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM seen_jobs WHERE id = ?", (job_id,)).fetchone()
        return row is not None


def mark_seen(job: dict) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO seen_jobs
                (id, title, company, location, url, source, posted_at, first_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            job["id"], job["title"], job["company"],
            job.get("location", ""), job["url"],
            job["source"], job["posted_at"]
        ))
        conn.commit()
