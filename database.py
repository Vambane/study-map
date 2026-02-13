"""
Normalized database layer for Study Map.

Schema:
  - topics:       unique topic/title entries
  - skills:       unique skill/course names
  - entries:      each learning session (links to a topic)
  - entry_skills: many-to-many bridge between entries and skills
  - connections:  AI-discovered relationships between entries
  - blindspots:   AI-suggested areas to explore next
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "study_map.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS topics (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL UNIQUE,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS skills (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS entries (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id            INTEGER NOT NULL REFERENCES topics(id),
            summary             TEXT NOT NULL,
            ai_classification   TEXT,          -- JSON blob from Claude
            created_at          TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS entry_skills (
            entry_id    INTEGER NOT NULL REFERENCES entries(id),
            skill_id    INTEGER NOT NULL REFERENCES skills(id),
            PRIMARY KEY (entry_id, skill_id)
        );

        CREATE TABLE IF NOT EXISTS connections (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            source_entry_id     INTEGER NOT NULL REFERENCES entries(id),
            target_entry_id     INTEGER NOT NULL REFERENCES entries(id),
            relationship        TEXT NOT NULL,
            strength            REAL NOT NULL DEFAULT 0.5,
            created_at          TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS blindspots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id    INTEGER NOT NULL REFERENCES entries(id),
            suggestion  TEXT NOT NULL,
            category    TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    # Migrations for new columns (idempotent – ignores if already exists)
    migrations = [
        "ALTER TABLE connections ADD COLUMN explanation TEXT",
        "ALTER TABLE blindspots ADD COLUMN why_important TEXT",
        "ALTER TABLE blindspots ADD COLUMN how_it_helps TEXT",
        "ALTER TABLE entries ADD COLUMN enhanced_summary TEXT",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()
    conn.close()


# ── Topic helpers ────────────────────────────────────────────

def get_or_create_topic(title: str) -> int:
    conn = get_connection()
    row = conn.execute("SELECT id FROM topics WHERE title = ?", (title,)).fetchone()
    if row:
        topic_id = row["id"]
    else:
        cur = conn.execute("INSERT INTO topics (title) VALUES (?)", (title,))
        topic_id = cur.lastrowid
        conn.commit()
    conn.close()
    return topic_id


def get_all_topics() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM topics ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Skill helpers ────────────────────────────────────────────

def get_or_create_skill(name: str) -> int:
    conn = get_connection()
    row = conn.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()
    if row:
        skill_id = row["id"]
    else:
        cur = conn.execute("INSERT INTO skills (name) VALUES (?)", (name,))
        skill_id = cur.lastrowid
        conn.commit()
    conn.close()
    return skill_id


def get_all_skills() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM skills ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Entry helpers ────────────────────────────────────────────

def create_entry(topic_id: int, summary: str, skill_ids: list[int],
                 ai_classification: dict | None = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO entries (topic_id, summary, ai_classification) VALUES (?, ?, ?)",
        (topic_id, summary, json.dumps(ai_classification) if ai_classification else None),
    )
    entry_id = cur.lastrowid
    for sid in skill_ids:
        conn.execute(
            "INSERT OR IGNORE INTO entry_skills (entry_id, skill_id) VALUES (?, ?)",
            (entry_id, sid),
        )
    conn.commit()
    conn.close()
    return entry_id


def get_all_entries() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT e.id, e.topic_id, t.title AS topic_title, e.summary,
               e.enhanced_summary, e.ai_classification, e.created_at,
               GROUP_CONCAT(s.name, ', ') AS skills
        FROM entries e
        JOIN topics t ON t.id = e.topic_id
        LEFT JOIN entry_skills es ON es.entry_id = e.id
        LEFT JOIN skills s ON s.id = es.skill_id
        GROUP BY e.id
        ORDER BY e.created_at DESC
    """).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        if d["ai_classification"]:
            d["ai_classification"] = json.loads(d["ai_classification"])
        results.append(d)
    return results


def get_entry_by_id(entry_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("""
        SELECT e.id, e.topic_id, t.title AS topic_title, e.summary,
               e.enhanced_summary, e.ai_classification, e.created_at,
               GROUP_CONCAT(s.name, ', ') AS skills
        FROM entries e
        JOIN topics t ON t.id = e.topic_id
        LEFT JOIN entry_skills es ON es.entry_id = e.id
        LEFT JOIN skills s ON s.id = es.skill_id
        WHERE e.id = ?
        GROUP BY e.id
    """, (entry_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    if d["ai_classification"]:
        d["ai_classification"] = json.loads(d["ai_classification"])
    return d


# ── Connection helpers ───────────────────────────────────────

def add_connection(source_id: int, target_id: int, relationship: str,
                   strength: float = 0.5, explanation: str | None = None):
    conn = get_connection()
    conn.execute(
        """INSERT INTO connections (source_entry_id, target_entry_id, relationship, strength, explanation)
           VALUES (?, ?, ?, ?, ?)""",
        (source_id, target_id, relationship, strength, explanation),
    )
    conn.commit()
    conn.close()


def get_all_connections() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT c.*,
               t1.title AS source_topic, t2.title AS target_topic
        FROM connections c
        JOIN entries e1 ON e1.id = c.source_entry_id
        JOIN entries e2 ON e2.id = c.target_entry_id
        JOIN topics t1 ON t1.id = e1.topic_id
        JOIN topics t2 ON t2.id = e2.topic_id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Blindspot helpers ────────────────────────────────────────

def add_blindspot(entry_id: int, suggestion: str, category: str | None = None,
                  why_important: str | None = None, how_it_helps: str | None = None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO blindspots (entry_id, suggestion, category, why_important, how_it_helps) VALUES (?, ?, ?, ?, ?)",
        (entry_id, suggestion, category, why_important, how_it_helps),
    )
    conn.commit()
    conn.close()


def update_enhanced_summary(entry_id: int, enhanced_summary: str):
    conn = get_connection()
    conn.execute(
        "UPDATE entries SET enhanced_summary = ? WHERE id = ?",
        (enhanced_summary, entry_id),
    )
    conn.commit()
    conn.close()


def get_all_blindspots() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT b.*, t.title AS topic_title
        FROM blindspots b
        JOIN entries e ON e.id = b.entry_id
        JOIN topics t ON t.id = e.topic_id
        ORDER BY b.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
