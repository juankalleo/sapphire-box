"""App directories and persisted settings.

A per-user data dir, plus a library path that defaults sensibly but can
be overridden via a small text file. `platformdirs` handles the
per-OS conventions so this works the same on Linux/macOS/Windows.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

from platformdirs import PlatformDirs

APP_NAME = "sapphirebox"
APP_AUTHOR = "sapphirebox"
LEGACY_APP_NAME = "hooperbox"
LEGACY_APP_AUTHOR = "hooperbox"

_dirs = PlatformDirs(APP_NAME, APP_AUTHOR)
_legacy_dirs = PlatformDirs(LEGACY_APP_NAME, LEGACY_APP_AUTHOR)


def _migrate_legacy_dir(old_path: Path, new_path: Path) -> bool:
    if old_path.exists() and not new_path.exists():
        new_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_path), str(new_path))
        return True
    return False


def _rewrite_stale_local_paths(old_data_dir: Path, new_data_dir: Path) -> None:
    """Moving the data dir relocates app.db (and the library/books folders
    inside it) as a unit, but every Manga/Book.local_path already written
    into it is a plain text string captured at download time — the move
    doesn't touch that text, so rows from before the rename still say the
    old (now nonexistent) directory and the library can't find them
    anymore. Rewrite those strings in place, once, right after the move."""
    db_path = new_data_dir / "app.db"
    if not db_path.exists():
        return
    old_prefix, new_prefix = str(old_data_dir), str(new_data_dir)
    conn = sqlite3.connect(str(db_path))
    try:
        for table in ("manga", "books"):
            try:
                conn.execute(
                    f"UPDATE {table} SET local_path = REPLACE(local_path, ?, ?) WHERE local_path LIKE ?",
                    (old_prefix, new_prefix, f"{old_prefix}%"),
                )
            except sqlite3.OperationalError:
                continue
        conn.commit()
    finally:
        conn.close()


def get_data_dir() -> Path:
    override = os.getenv("SAPPHIREBOX_DATA_DIR")
    if override:
        p = Path(override).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p

    p = Path(_dirs.user_data_dir)
    old = Path(_legacy_dirs.user_data_dir)
    if _migrate_legacy_dir(old, p):
        _rewrite_stale_local_paths(old, p)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_cache_dir() -> Path:
    override = os.getenv("SAPPHIREBOX_CACHE_DIR")
    if override:
        p = Path(override).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p

    p = Path(_dirs.user_cache_dir)
    _migrate_legacy_dir(Path(_legacy_dirs.user_cache_dir), p)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_logs_dir() -> Path:
    p = get_data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_database_path() -> Path:
    return get_data_dir() / "app.db"


def _library_override_file() -> Path:
    return get_data_dir() / "library_path.txt"


def get_library_path() -> Path:
    """Resolve the manga/manhwa library folder.

    Precedence: an explicit override written by `set_library_path`, else a
    sane per-OS default under the user's data dir.
    """
    override_file = _library_override_file()
    if override_file.exists():
        raw = override_file.read_text(encoding="utf-8").splitlines()
        first = raw[0].strip() if raw else ""
        if first:
            path = Path(first)
            path.mkdir(parents=True, exist_ok=True)
            return path

    default = get_data_dir() / "library"
    default.mkdir(parents=True, exist_ok=True)
    return default


def set_library_path(path: Path) -> None:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    _library_override_file().write_text(str(path), encoding="utf-8")


def get_books_library_path() -> Path:
    """Separate shelf for downloaded books, sibling to the manga library."""
    p = get_library_path().parent / "books"
    p.mkdir(parents=True, exist_ok=True)
    return p


def initialize_app_paths() -> None:
    get_library_path()
    get_books_library_path()
    get_cache_dir()
    get_logs_dir()


def compute_storage_stats() -> dict:
    """Walks the manga + books library folders and totals file count/size."""
    total_bytes = 0
    file_count = 0
    for root in (get_library_path(), get_books_library_path()):
        for path in root.rglob("*"):
            if path.is_file():
                try:
                    total_bytes += path.stat().st_size
                    file_count += 1
                except OSError:
                    continue
    return {"fileCount": file_count, "totalBytes": total_bytes}
