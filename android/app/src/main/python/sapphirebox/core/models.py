"""Shared data shapes used across the manga/books/library modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


@dataclass
class Manga:
    id: str
    title: str
    source_id: str
    source_name: str
    cover_path: str | None = None
    synopsis: str | None = None
    status: str = "unknown"
    rating: float = 0.0
    language: str = "Português"
    local_path: str = ""
    total_chapters: int = 0
    downloaded_chapters: int = 0
    chapter_options: list["MangaChapterOption"] = field(default_factory=list)
    last_updated: str = field(default_factory=now_iso)


@dataclass
class MangaChapterOption:
    index: int
    label: str
    url: str | None = None
    downloaded: bool = False


@dataclass
class Chapter:
    id: str
    manga_id: str
    chapter_number: float
    title: str | None = None
    url: str | None = None
    downloaded: bool = False
    file_path: str | None = None
    pages: int = 0


@dataclass
class ChapterMeta:
    number: float
    volume: int | None
    date: str
    scanlator: str
    filename: str


@dataclass
class MangaIndex:
    """Metadata file each downloaded manga folder carries (`index.json`)."""

    id: str
    title: str
    authors: list[str]
    rating: float
    state: str
    chapters: dict[str, ChapterMeta]
    app_version: str = "sapphirebox"


@dataclass
class BookFileOption:
    format: str
    url: str
    label: str | None = None
    size_bytes: int | None = None
    size_label: str | None = None


@dataclass
class Book:
    id: str
    title: str
    source_id: str
    source_name: str
    author: str | None = None
    cover_path: str | None = None
    synopsis: str | None = None
    language: str | None = None
    format: str = "epub"
    pages: int | None = None
    year: str | None = None
    category: str | None = None
    local_path: str | None = None
    file_size_bytes: int | None = None
    file_options: list[BookFileOption] = field(default_factory=list)
    last_updated: str = field(default_factory=now_iso)


@dataclass
class DownloadJob:
    id: str
    status: str = "pending"  # pending | running | manual_required | completed | cancelled | error
    progress: int = 0
    dest: str | None = None
    title: str | None = None
    cover_path: str | None = None
    last_stdout: str | None = None
    last_stderr: str | None = None
    error: str | None = None
    # Enough of the original request to retry from scratch — filled in by
    # web/downloads.py, read back by the /retry endpoint. `domain` is
    # "manga" or "book"; the rest map straight onto start_*_download's
    # params (irrelevant ones stay None for the other domain).
    domain: str | None = None
    source_id: str | None = None
    item_id: str | None = None
    chapters: str | None = None
    format: str | None = None
    author: str | None = None
    source_name: str | None = None
    manual_url: str | None = None
