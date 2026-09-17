"""Project Gutenberg — first book source, chosen because it's the least
friction possible: public-domain texts, a clean JSON search API
(Gutendex, a well-known community mirror of the Gutenberg catalog), and
direct epub/txt links with no login or rate-limit dance. Mirrors the
shape of PiraChest's core/books/sources/gutenberg.py.
"""
from __future__ import annotations

from pathlib import Path

from sapphirebox.core.cache import cache
from sapphirebox.core.downloader import new_client, safe_filename
from sapphirebox.core.models import Book
from sapphirebox.books.sources.base import BookSource

API_BASE = "https://gutendex.com/books"
_CACHE_NS = "gutenberg:formats"


def _best_format(formats: dict[str, str]) -> tuple[str, str] | None:
    for mime, ext in (("application/epub+zip", "epub"), ("text/plain; charset=utf-8", "txt"), ("text/plain", "txt")):
        url = formats.get(mime)
        if url:
            return url, ext
    return None


def _cover_url(formats: dict[str, str]) -> str | None:
    for mime, url in formats.items():
        if mime.startswith("image/"):
            return url
    return None


def _to_book(item: dict) -> Book | None:
    formats = item.get("formats", {})
    best = _best_format(formats)
    if best is None:
        return None
    url, ext = best

    book_id = f"gutenberg-{item['id']}"
    cache.set(f"{_CACHE_NS}:{book_id}", url, ttl=3600)

    authors = ", ".join(a.get("name", "") for a in item.get("authors", [])) or None
    languages = item.get("languages") or []
    return Book(
        id=book_id,
        title=item.get("title", "Sem título"),
        author=authors,
        source_id="gutenberg",
        source_name="Project Gutenberg",
        cover_path=_cover_url(formats),
        language=languages[0] if languages else None,
        format=ext,
    )


def search(query: str, limit: int = 20, page: int = 1) -> list[Book]:
    params = {"search": query} if query.strip() else {}
    if page > 1:
        params["page"] = page
    with new_client(timeout=15) as client:
        resp = client.get(API_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()

    books: list[Book] = []
    for item in data.get("results", []):
        book = _to_book(item)
        if book:
            books.append(book)
        if len(books) >= limit:
            break
    return books


def _resolve_download_url(book: Book) -> str:
    cached = cache.get(f"{_CACHE_NS}:{book.id}")
    if cached:
        return cached

    gutenberg_id = book.id.removeprefix("gutenberg-")
    with new_client(timeout=15) as client:
        resp = client.get(f"{API_BASE}/{gutenberg_id}")
        resp.raise_for_status()
        formats = resp.json().get("formats", {})
    best = _best_format(formats)
    if best is None:
        raise RuntimeError(f"No downloadable epub/txt found for Gutenberg book {gutenberg_id}")
    return best[0]


def download(book: Book, dest_dir: Path) -> Book:
    url = _resolve_download_url(book)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with new_client(timeout=60) as client:
        resp = client.get(url)
        resp.raise_for_status()
        content = resp.content

    filename = f"{safe_filename(book.title)}.{book.format}"
    path = dest_dir / filename
    path.write_bytes(content)

    book.local_path = str(path)
    book.file_size_bytes = len(content)
    return book


class GutenbergSource(BookSource):
    id = "gutenberg"
    name = "Project Gutenberg"

    def search(self, query: str, limit: int = 20, page: int = 1) -> list[Book]:
        return search(query, limit, page)

    def download(self, book: Book, dest_dir: Path, on_progress=None) -> Book:
        return download(book, dest_dir)
