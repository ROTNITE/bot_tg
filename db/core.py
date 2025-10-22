# app/db/core.py
from __future__ import annotations

import aiosqlite
from app.config import DB_PATH

# ---------------------- Schema & Migrations ----------------------

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS recent_partners(
  u_id INTEGER NOT NULL,
  partner_id INTEGER NOT NULL,
  block_left INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(u_id, partner_id)
);

PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users(
  tg_id INTEGER PRIMARY KEY,
  gender TEXT,
  seeking TEXT,
  reveal_ready INTEGER DEFAULT 0,
  first_name TEXT,
  last_name TEXT,
  faculty TEXT,
  age INTEGER,
  about TEXT,
  username TEXT,
  photo1 TEXT,
  photo2 TEXT,
  photo3 TEXT,
  created_at INTEGER DEFAULT (strftime('%s','now')),
  updated_at INTEGER DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS shop_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  price INTEGER NOT NULL,
  type TEXT NOT NULL,
  payload TEXT,
  is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ratings(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  from_user INTEGER NOT NULL,
  to_user INTEGER NOT NULL,
  stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
  ts INTEGER DEFAULT (strftime('%s','now')),
  UNIQUE(match_id, from_user)
);

CREATE INDEX IF NOT EXISTS idx_ratings_to ON ratings(to_user);

CREATE TABLE IF NOT EXISTS complaints(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  from_user INTEGER NOT NULL,
  about_user INTEGER NOT NULL,
  text TEXT,
  ts INTEGER DEFAULT (strftime('%s','now')),
  status TEXT DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS purchases(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  item_id INTEGER NOT NULL,
  ts INTEGER DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS user_statuses(
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  PRIMARY KEY(user_id, title)
);

CREATE TABLE IF NOT EXISTS support_msgs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_user INTEGER NOT NULL,
  to_admin INTEGER,
  orig_msg_id INTEGER,
  text TEXT,
  ts INTEGER DEFAULT (strftime('%s','now')),
  status TEXT DEFAULT 'open'
);

CREATE TRIGGER IF NOT EXISTS users_updated
AFTER UPDATE ON users
BEGIN
  UPDATE users SET updated_at=strftime('%s','now') WHERE tg_id=NEW.tg_id;
END;

CREATE TABLE IF NOT EXISTS queue(
  tg_id INTEGER PRIMARY KEY,
  gender TEXT,
  seeking TEXT,
  ts INTEGER
);

CREATE TABLE IF NOT EXISTS matches(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  a_id INTEGER,
  b_id INTEGER,
  active INTEGER DEFAULT 1,
  a_reveal INTEGER DEFAULT 0,
  b_reveal INTEGER DEFAULT 0,
  started_at INTEGER DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS referrals(
  inviter INTEGER NOT NULL,
  invited INTEGER PRIMARY KEY,
  ts INTEGER DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY,
  value TEXT
);

CREATE INDEX IF NOT EXISTS idx_matches_active ON matches(active);
"""

# (table, column, alter-sql)
ALTERS = [
    ("users", "role",         "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'"),
    ("users", "points",       "ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0"),
    ("users", "status_title", "ALTER TABLE users ADD COLUMN status_title TEXT"),
    ("users", "last_daily",   "ALTER TABLE users ADD COLUMN last_daily INTEGER DEFAULT 0"),
    ("users", "sub_verified", "ALTER TABLE users ADD COLUMN sub_verified INTEGER DEFAULT 0"),
]

# ---------------------- Connection helper ----------------------

def db():
    """Open a new aiosqlite connection to the bot database."""
    return aiosqlite.connect(DB_PATH)

# ---------------------- Initializer ----------------------

async def init_db():
    """Create base schema, apply soft ALTERs, and run lightweight migrations."""
    async with db() as conn:
        # base schema + WAL pragma
        await conn.executescript(CREATE_SQL)

        # soft ALTERs (idempotent)
        for table, col, sql in ALTERS:
            cur = await conn.execute(f"PRAGMA table_info({table})")
            cols = [r[1] for r in await cur.fetchall()]
            if col not in cols:
                try:
                    await conn.execute(sql)
                except Exception:
                    # ignore concurrent/multi-run race or older SQLite quirks
                    pass

        # referrals migration + opaque ref_codes
        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='referrals'"
        )
        has_ref = await cur.fetchone()
        if has_ref:
            cur = await conn.execute("PRAGMA table_info(referrals)")
            cols = {r[1] for r in await cur.fetchall()}
            if "inviter" not in cols:
                await conn.execute("ALTER TABLE referrals ADD COLUMN inviter INTEGER")
            if "ts" not in cols:
                await conn.execute(
                    "ALTER TABLE referrals ADD COLUMN ts INTEGER DEFAULT (strftime('%s','now'))"
                )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ref_codes(
                  code TEXT PRIMARY KEY,
                  inviter INTEGER NOT NULL
                )
                """
            )

        await conn.commit()

__all__ = ["db", "init_db", "CREATE_SQL", "ALTERS"]
