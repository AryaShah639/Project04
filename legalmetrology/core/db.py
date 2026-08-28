"""Database layer for the Legal Metrology Compliance System (SQLite)."""
import os, sqlite3, json, time, uuid
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
UPLOAD_DIR = os.path.join(BASE, "uploads")
GEN_DIR = os.path.join(BASE, "generated")
for d in (DATA_DIR, UPLOAD_DIR, GEN_DIR):
    os.makedirs(d, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "lmcs.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','inspector','viewer')),
  designation TEXT DEFAULT '',
  state TEXT DEFAULT '',
  is_active INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  category TEXT DEFAULT '',
  brand TEXT DEFAULT '',
  manufacturer TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scan_code TEXT UNIQUE NOT NULL,
  product_id INTEGER,
  product_name TEXT NOT NULL,
  category TEXT DEFAULT '',
  source TEXT NOT NULL DEFAULT 'image',        -- image | listing
  file_path TEXT DEFAULT '',                   -- evidence image
  listing_text TEXT DEFAULT '',
  pkg_dims_cm TEXT DEFAULT '',                 -- e.g. "10x8" or "cyl:20x25"
  pdp_area_cm2 REAL,
  dpi REAL,
  raw_text TEXT DEFAULT '',
  extracted_json TEXT DEFAULT '{}',
  checks_json TEXT DEFAULT '[]',
  font_json TEXT DEFAULT '[]',
  overall_status TEXT DEFAULT 'PENDING',
  score INTEGER DEFAULT 0,
  notes TEXT DEFAULT '',
  review_status TEXT DEFAULT 'PENDING',        -- PENDING | VERIFIED | QUARANTINED
  created_by INTEGER,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS inspections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scan_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  location TEXT DEFAULT '',
  inspector TEXT DEFAULT '',
  findings TEXT DEFAULT '',
  action_taken TEXT DEFAULT '',
  notice_ref TEXT DEFAULT '',
  status TEXT DEFAULT 'OPEN',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scan_id INTEGER NOT NULL,
  fmt TEXT NOT NULL,                           -- pdf | docx | csv
  file_path TEXT NOT NULL,
  created_by INTEGER,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  username TEXT DEFAULT '',
  action TEXT NOT NULL,
  entity TEXT DEFAULT '',
  detail TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS auth_tokens (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
"""

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    # lightweight migrations
    for col, ddl in (("is_photo", "INTEGER DEFAULT 0"),
                     ("dpi_source", "TEXT DEFAULT 'meta'")):
        try:
            conn.execute(f"ALTER TABLE scans ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

def new_scan_code():
    return "LM-" + datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6].upper()

def now_str():
    return datetime.now().strftime("%d-%m-%Y %H:%M:%S")

def audit(user, action, entity="", detail=""):
    conn = get_conn()
    conn.execute("INSERT INTO audit_log(user_id, username, action, entity, detail) VALUES (?,?,?,?,?)",
                 (user["id"] if user else None, user["username"] if user else "system", action, entity, detail[:2000]))
    conn.commit(); conn.close()
