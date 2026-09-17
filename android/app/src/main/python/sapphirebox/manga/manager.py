"""Orchestration for manga search/listing/download.

Cache-first search with a live-scrape fallback, and downloads delegated
straight to whichever source implements them. No external engine here —
every manga source is plain Python, which is what keeps this portable to
Android later instead of depending on a JVM subprocess.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from sapphirebox.core import relevance
from sapphirebox.core.config import get_library_path
from sapphirebox.core.downloader import slug_from_url
from sapphirebox.core.models import Manga, MangaChapterOption
from sapphirebox.library import repository
from sapphirebox.manga.sources import registry

ProgressCallback = Callable[[int, str], None]


def search_cache(query: str) -> list[Manga]:
    """DB-only search."""
    if not query.strip():
        return []
    return repository.search_by_title(query)


def list_by_source(source_id: str, page: int = 1, page_size: int = 20) -> tuple[list[Manga], int]:
    """Cache first, live scrape as fallback."""
    cached, total_pages = repository.list_by_source_paginated(source_id, page, page_size)
    if cached:
        return cached, total_pages

    source = registry.get_source(source_id)
    if source is None:
        return [], 1
    results, total_pages = source.search("", page)
    results = relevance.clean_listing(results)
    return results[:page_size], max(total_pages, 1)


def search_web(source_id: str, query: str, page: int = 1, page_size: int = 20) -> tuple[list[Manga], int]:
    """Always-live search."""
    source = registry.get_source(source_id)
    if source is None:
        return [], 1
    results, total_pages = source.search(query, page)
    results = relevance.clean_listing(results)
    results = relevance.rank(results, query)
    return results[:page_size], total_pages


def search_all(query: str, page_size: int = 40) -> list[Manga]:
    """Searches every implemented manga source and merges the first page of
    each — cross-source pagination isn't worth the complexity here, this is
    for the "todas as fontes" option in search. Merged results are ranked
    by relevance to `query` rather than left in source order, so a source
    checked later doesn't get buried behind an earlier one's noise."""
    merged: list[Manga] = []
    for info in registry.load_source_infos():
        if not info.has_python_source:
            continue
        source = registry.get_source(info.id)
        if source is None:
            continue
        try:
            results, _ = source.search(query, 1)
        except Exception:
            continue
        merged.extend(results)
    merged = relevance.clean_listing(merged)
    return relevance.rank(merged, query)[:page_size]


def get_details(source_id: str, manga_id: str) -> Manga | None:
    source = registry.get_source(source_id)
    manga = source.get_details(manga_id) if source else None
    if manga:
        saved = repository.get_manga_by_id(manga_id)
        if saved:
            manga.local_path = manga.local_path or saved.local_path
            manga.downloaded_chapters = manga.downloaded_chapters or saved.downloaded_chapters
            manga.total_chapters = manga.total_chapters or saved.total_chapters
        manga.chapter_options = list_chapters(source_id, manga_id)
        if saved or manga.local_path:
            repository.upsert_manga(manga)
    return manga


def _downloaded_chapter_labels(manga_id: str) -> set[str]:
    labels: set[str] = set()
    roots: list[Path] = []
    saved = repository.get_manga_by_id(manga_id)
    if saved and saved.local_path:
        roots.append(Path(saved.local_path))
    roots.append(get_library_path() / slug_from_url(manga_id, "manga"))

    for root in roots:
        if not root.is_dir():
            continue
        for path in root.glob("chapter_*.cbz"):
            raw = path.stem.removeprefix("chapter_")
            labels.add(raw)
            labels.add(raw.replace("_", "."))
    return labels


def list_chapters(source_id: str, manga_id: str) -> list[MangaChapterOption]:
    source = registry.get_source(source_id)
    if source is None:
        return []
    chapters = source.list_chapters(manga_id)
    downloaded = _downloaded_chapter_labels(manga_id)
    for chapter in chapters:
        file_label = chapter.label.replace(".", "_")
        chapter.downloaded = chapter.label in downloaded or file_label in downloaded
    return chapters


def download(
    source_id: str,
    manga_id: str,
    chapters: str = "all",
    fmt: str = "cbz",
    dest_root: Path | None = None,
    on_progress: ProgressCallback | None = None,
    title: str | None = None,
) -> Manga:
    source = registry.get_source(source_id)
    if source is None:
        raise RuntimeError(f"Fonte '{source_id}' não tem um downloader implementado ainda")

    dest_root = dest_root or get_library_path()
    per_manga_dest = dest_root / slug_from_url(manga_id, "manga")
    per_manga_dest.mkdir(parents=True, exist_ok=True)

    manga = source.download_chapters(manga_id, per_manga_dest, chapters, fmt, on_progress)
    if title:
        # The downloader falls back to a folder-name-derived title (no
        # index.json to read one from) — prefer the real title the caller
        # already had from search results when there is one.
        manga.title = title
    repository.upsert_manga(manga)
    return manga
