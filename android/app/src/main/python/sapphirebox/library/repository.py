"""SQLite access for manga and books — port of library/sqlite_repository.rs."""
from __future__ import annotations

import sqlite3

from sapphirebox.core import db
from sapphirebox.core.models import Book, Manga


def _row_to_manga(row: sqlite3.Row) -> Manga:
    return Manga(
        id=row["id"],
        title=row["title"],
        source_id=row["source_id"],
        source_name=row["source_name"],
        cover_path=row["cover_path"],
        synopsis=row["synopsis"],
        status=row["status"] or "unknown",
        rating=row["rating"] or 0.0,
        language=row["language"] or "Português",
        local_path=row["local_path"] or "",
        total_chapters=row["total_chapters"] or 0,
        downloaded_chapters=row["downloaded_chapters"] or 0,
        last_updated=row["last_updated"] or "",
    )


_MANGA_COLUMNS = (
    "id, title, source_id, source_name, cover_path, synopsis, status, rating, "
    "language, local_path, total_chapters, downloaded_chapters, last_updated"
)


def upsert_manga(manga: Manga) -> None:
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO manga (
                id, title, source_id, source_name, cover_path, synopsis,
                status, rating, language, local_path, total_chapters,
                downloaded_chapters, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, source_id=excluded.source_id, source_name=excluded.source_name,
                cover_path=excluded.cover_path, synopsis=excluded.synopsis, status=excluded.status,
                rating=excluded.rating, language=excluded.language, local_path=excluded.local_path,
                total_chapters=excluded.total_chapters, downloaded_chapters=excluded.downloaded_chapters,
                last_updated=excluded.last_updated
            """,
            (
                manga.id, manga.title, manga.source_id, manga.source_name, manga.cover_path,
                manga.synopsis, manga.status, manga.rating, manga.language, manga.local_path,
                manga.total_chapters, manga.downloaded_chapters, manga.last_updated,
            ),
        )


def get_manga_by_id(manga_id: str) -> Manga | None:
    with db.cursor() as cur:
        cur.execute(f"SELECT {_MANGA_COLUMNS} FROM manga WHERE id = ?", (manga_id,))
        row = cur.fetchone()
    return _row_to_manga(row) if row else None


def search_by_title(query: str, limit: int = 50) -> list[Manga]:
    with db.cursor() as cur:
        cur.execute(
            f"SELECT {_MANGA_COLUMNS} FROM manga WHERE title LIKE ? ORDER BY title LIMIT ?",
            (f"%{query}%", limit),
        )
        rows = cur.fetchall()
    return [_row_to_manga(r) for r in rows]


def list_by_source_paginated(source_id: str, page: int = 1, page_size: int = 20) -> tuple[list[Manga], int]:
    page = max(page, 1)
    offset = (page - 1) * page_size
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS count FROM manga WHERE source_id = ?", (source_id,))
        total = cur.fetchone()["count"]
        cur.execute(
            f"SELECT {_MANGA_COLUMNS} FROM manga WHERE source_id = ? ORDER BY title LIMIT ? OFFSET ?",
            (source_id, page_size, offset),
        )
        rows = cur.fetchall()
    total_pages = max((total + page_size - 1) // page_size, 1)
    return [_row_to_manga(r) for r in rows], total_pages


def list_library(page: int = 1, page_size: int = 20) -> tuple[list[Manga], int]:
    page = max(page, 1)
    offset = (page - 1) * page_size
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS count FROM manga WHERE TRIM(COALESCE(local_path, '')) <> ''")
        total = cur.fetchone()["count"]
        cur.execute(
            f"""SELECT {_MANGA_COLUMNS} FROM manga
                WHERE TRIM(COALESCE(local_path, '')) <> ''
                ORDER BY last_updated DESC LIMIT ? OFFSET ?""",
            (page_size, offset),
        )
        rows = cur.fetchall()
    total_pages = max((total + page_size - 1) // page_size, 1)
    return [_row_to_manga(r) for r in rows], total_pages


def delete_manga(manga_id: str) -> None:
    with db.cursor() as cur:
        cur.execute("DELETE FROM manga WHERE id = ?", (manga_id,))


# --- Books -----------------------------------------------------------------

_BOOK_COLUMNS = (
    "id, title, author, source_id, source_name, cover_path, synopsis, "
    "language, format, local_path, file_size_bytes, last_updated"
)


def _row_to_book(row: sqlite3.Row) -> Book:
    return Book(
        id=row["id"],
        title=row["title"],
        author=row["author"],
        source_id=row["source_id"],
        source_name=row["source_name"],
        cover_path=row["cover_path"],
        synopsis=row["synopsis"],
        language=row["language"],
        format=row["format"] or "epub",
        local_path=row["local_path"],
        file_size_bytes=row["file_size_bytes"],
        last_updated=row["last_updated"] or "",
    )


def get_book_by_id(book_id: str) -> Book | None:
    with db.cursor() as cur:
        cur.execute(f"SELECT {_BOOK_COLUMNS} FROM books WHERE id = ?", (book_id,))
        row = cur.fetchone()
    return _row_to_book(row) if row else None


def upsert_book(book: Book) -> None:
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO books (
                id, title, author, source_id, source_name, cover_path,
                synopsis, language, format, local_path, file_size_bytes, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, author=excluded.author, source_id=excluded.source_id,
                source_name=excluded.source_name, cover_path=excluded.cover_path,
                synopsis=excluded.synopsis, language=excluded.language, format=excluded.format,
                local_path=excluded.local_path, file_size_bytes=excluded.file_size_bytes,
                last_updated=excluded.last_updated
            """,
            (
                book.id, book.title, book.author, book.source_id, book.source_name, book.cover_path,
                book.synopsis, book.language, book.format, book.local_path, book.file_size_bytes,
                book.last_updated,
            ),
        )


def list_downloaded_books(page: int = 1, page_size: int = 20) -> tuple[list[Book], int]:
    page = max(page, 1)
    offset = (page - 1) * page_size
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS count FROM books WHERE TRIM(COALESCE(local_path, '')) <> ''")
        total = cur.fetchone()["count"]
        cur.execute(
            f"""SELECT {_BOOK_COLUMNS} FROM books
                WHERE TRIM(COALESCE(local_path, '')) <> ''
                ORDER BY last_updated DESC LIMIT ? OFFSET ?""",
            (page_size, offset),
        )
        rows = cur.fetchall()
    total_pages = max((total + page_size - 1) // page_size, 1)
    return [_row_to_book(r) for r in rows], total_pages


def delete_book(book_id: str) -> None:
    with db.cursor() as cur:
        cur.execute("DELETE FROM books WHERE id = ?", (book_id,))


def delete_downloaded_manga() -> None:
    with db.cursor() as cur:
        cur.execute("DELETE FROM manga WHERE TRIM(COALESCE(local_path, '')) <> ''")


def delete_downloaded_books() -> None:
    with db.cursor() as cur:
        cur.execute("DELETE FROM books WHERE TRIM(COALESCE(local_path, '')) <> ''")


# --- Reading position (resume where you left off) ---------------------------


def get_reading_state(item_id: str) -> dict | None:
    with db.cursor() as cur:
        cur.execute(
            "SELECT item_id, kind, chapter_file, page_index, location FROM reading_state WHERE item_id = ?",
            (item_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "itemId": row["item_id"],
        "kind": row["kind"],
        "chapterFile": row["chapter_file"],
        "pageIndex": row["page_index"],
        "location": row["location"],
    }


def save_reading_state(
    item_id: str,
    kind: str,
    chapter_file: str | None = None,
    page_index: int | None = None,
    location: str | None = None,
) -> None:
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO reading_state (item_id, kind, chapter_file, page_index, location, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(item_id) DO UPDATE SET
                kind=excluded.kind, chapter_file=excluded.chapter_file,
                page_index=excluded.page_index, location=excluded.location,
                updated_at=CURRENT_TIMESTAMP
            """,
            (item_id, kind, chapter_file, page_index, location),
        )


def delete_reading_state(item_id: str) -> None:
    with db.cursor() as cur:
        cur.execute("DELETE FROM reading_state WHERE item_id = ?", (item_id,))


def delete_all_reading_state() -> None:
    with db.cursor() as cur:
        cur.execute("DELETE FROM reading_state")
