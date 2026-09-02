import sqlite3
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS phones (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    url TEXT,
    image_url TEXT
);
CREATE TABLE IF NOT EXISTS specs (
    id INTEGER PRIMARY KEY,
    phone_id INTEGER NOT NULL REFERENCES phones(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    spec_name TEXT NOT NULL,
    spec_value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY,
    phone_id INTEGER NOT NULL REFERENCES phones(id) ON DELETE CASCADE,
    chunk TEXT NOT NULL,
    vector BLOB NOT NULL
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def save_phone(name, url, image_url, specs):
    """specs: list of (category, spec_name, spec_value). Replaces any prior data."""
    with get_conn() as conn:
        old = conn.execute("SELECT id FROM phones WHERE name = ?", (name,)).fetchone()
        if old:
            conn.execute("DELETE FROM phones WHERE id = ?", (old["id"],))
        cur = conn.execute(
            "INSERT INTO phones (name, url, image_url) VALUES (?, ?, ?)",
            (name, url, image_url),
        )
        conn.executemany(
            "INSERT INTO specs (phone_id, category, spec_name, spec_value) VALUES (?, ?, ?, ?)",
            [(cur.lastrowid, c, n, v) for c, n, v in specs],
        )


def list_phones():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM phones ORDER BY name")]


def get_specs(phone_name):
    """All specs for a phone (case-insensitive name match). Returns None if unknown."""
    with get_conn() as conn:
        phone = conn.execute(
            "SELECT * FROM phones WHERE name = ? COLLATE NOCASE", (phone_name,)
        ).fetchone()
        if not phone:
            phone = conn.execute(
                "SELECT * FROM phones WHERE name LIKE ? COLLATE NOCASE ORDER BY LENGTH(name) LIMIT 1",
                (f"%{phone_name}%",),
            ).fetchone()
        if not phone:
            return None
        rows = conn.execute(
            "SELECT category, spec_name, spec_value FROM specs WHERE phone_id = ? ORDER BY id",
            (phone["id"],),
        ).fetchall()
        return {"phone": dict(phone), "specs": [dict(r) for r in rows]}


def save_embedding(phone_id, chunk, vector_blob):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO embeddings (phone_id, chunk, vector) VALUES (?, ?, ?)",
            (phone_id, chunk, vector_blob),
        )


def clear_embeddings():
    with get_conn() as conn:
        conn.execute("DELETE FROM embeddings")


def load_embeddings():
    with get_conn() as conn:
        return conn.execute(
            "SELECT e.chunk, e.vector, p.name AS phone_name "
            "FROM embeddings e JOIN phones p ON p.id = e.phone_id"
        ).fetchall()
