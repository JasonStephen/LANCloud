import sqlite3
from config import DB_PATH, DEFAULT_QUOTA_BYTES, DEFAULT_CLEANUP_INTERVAL_SECONDS

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  orig_name TEXT NOT NULL,
  stored_name TEXT NOT NULL UNIQUE,
  ext TEXT,
  mime TEXT,
  category TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  uploaded_at TEXT NOT NULL,
  expires_at TEXT,
  is_forever INTEGER NOT NULL DEFAULT 0,
  downloads INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)

    # 默认配置
    defaults = {
        "quota_bytes": str(4 * 1024 * 1024 * 1024),      # 4GB
        "max_request_bytes": str(15 * 1024 * 1024 * 1024),  # 15GB
        "max_file_bytes": str(1024 * 1024 * 1024),      # 1GB
        "cleanup_interval_seconds": "60",
    }

    for k, v in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
            (k, v)
        )

    conn.commit()
    conn.close()

def get_setting(key: str) -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else ""

def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()