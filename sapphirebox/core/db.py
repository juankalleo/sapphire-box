"""SQLite connection and schema.

One idempotent schema (manga, chapters, reading_progress, favorites,
downloads, sources, user_settings, books, reading_state) applied on first
connection — there's no prior database to migrate from, so plain `CREATE
TABLE IF NOT EXISTS` is enough.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sapphirebox.core.config import get_database_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS manga (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  source_id TEXT NOT NULL DEFAULT 'local',
  source_name TEXT NOT NULL,
  source_url TEXT,
  cover_path TEXT,
  synopsis TEXT,
  status TEXT,
  rating REAL,
  language TEXT DEFAULT 'pt-BR',
  local_path TEXT NOT NULL UNIQUE,
  total_chapters INTEGER,
  downloaded_chapters INTEGER,
  last_updated TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chapters (
  id TEXT PRIMARY KEY,
  manga_id TEXT NOT NULL,
  chapter_number REAL NOT NULL,
  title TEXT,
  url TEXT,
  downloaded BOOLEAN DEFAULT 0,
  file_path TEXT,
  pages INTEGER,
  size_bytes INTEGER,
  released_at TIMESTAMP,
  FOREIGN KEY (manga_id) REFERENCES manga(id) ON DELETE CASCADE,
  UNIQUE(manga_id, chapter_number)
);

CREATE TABLE IF NOT EXISTS reading_progress (
  id TEXT PRIMARY KEY,
  manga_id TEXT NOT NULL,
  chapter_id TEXT NOT NULL,
  current_page INTEGER,
  total_pages INTEGER,
  last_read TIMESTAMP,
  FOREIGN KEY (manga_id) REFERENCES manga(id) ON DELETE CASCADE,
  FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS favorites (
  id TEXT PRIMARY KEY,
  manga_id TEXT NOT NULL UNIQUE,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (manga_id) REFERENCES manga(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS downloads (
  id TEXT PRIMARY KEY,
  manga_id TEXT,
  chapter_ids TEXT,
  status TEXT DEFAULT 'pending',
  progress_percent INTEGER DEFAULT 0,
  current_file TEXT,
  error_message TEXT,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  FOREIGN KEY (manga_id) REFERENCES manga(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  language TEXT,
  enabled BOOLEAN DEFAULT 1,
  priority INTEGER DEFAULT 999,
  last_synced TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_settings (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Where the reader left off on a given manga/book, so reopening it (even
-- after quitting the app) picks back up instead of starting over. One row
-- per item; `chapter_file` is manga-only, `location` is a free-form
-- position marker whose meaning depends on `kind` (an epub CFI string, or
-- a 0..1 scroll fraction for plain-text/extracted-PDF-text reading).
CREATE TABLE IF NOT EXISTS reading_state (
  item_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  chapter_file TEXT,
  page_index INTEGER,
  location TEXT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- New for Sapphire Box: the books/epub module.
CREATE TABLE IF NOT EXISTS books (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  author TEXT,
  source_id TEXT NOT NULL,
  source_name TEXT NOT NULL,
  cover_path TEXT,
  synopsis TEXT,
  language TEXT,
  format TEXT,
  local_path TEXT UNIQUE,
  file_size_bytes INTEGER,
  last_updated TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_manga_title ON manga(title);
CREATE INDEX IF NOT EXISTS idx_manga_source ON manga(source_name);
CREATE INDEX IF NOT EXISTS idx_manga_source_id ON manga(source_id);
CREATE INDEX IF NOT EXISTS idx_chapters_manga ON chapters(manga_id);
CREATE INDEX IF NOT EXISTS idx_favorites_manga ON favorites(manga_id);
CREATE INDEX IF NOT EXISTS idx_downloads_status ON downloads(status);
CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
CREATE INDEX IF NOT EXISTS idx_books_source ON books(source_id);
"""

_local = threading.local()


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """One connection per thread, schema applied on first use."""
    if getattr(_local, "conn", None) is not None:
        return _local.conn

    path = db_path or get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    conn.commit()
    _local.conn = conn
    return conn


def reset_connection() -> None:
    """Drops the cached connection for this thread (mainly for tests that
    need a fresh, isolated database file)."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
    _local.conn = None


@contextmanager
def cursor() -> Iterator[sqlite3.Cursor]:
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
