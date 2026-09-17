"""Internet Archive — texts collection. Public search + metadata APIs, no
key required. Not every item has a downloadable file (some are
borrow-only or scans with no derived epub/pdf); `download` raises a clear
error in that case rather than silently returning nothing.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from sapphirebox.core.downloader import new_client, safe_filename
from sapphirebox.core.models import Book
from sapphirebox.books.sources.base import BookSource

SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata"
DOWNLOAD_URL = "https://archive.org/download"
COVER_URL = "https://archive.org/services/img"

_PREFERRED_EXTENSIONS = (".epub", ".pdf")


def _to_book(doc: dict) -> Book:
    identifier = doc["identifier"]
    creator = doc.get("creator")
    if isinstance(creator, list):
        creator = ", ".join(creator)
    language = doc.get("language")
    if isinstance(language, list):
        language = language[0] if language else None

    return Book(
        id=f"ia-{identifier}",
        title=doc.get("title", identifier),
        author=creator,
        source_id="internet_archive",
        source_name="Internet Archive",
        cover_path=f"{COVER_URL}/{identifier}",
        language=language,
        format="epub",
    )


def search(query: str, limit: int = 20, page: int = 1) -> list[Book]:
    params = {
        "q": f'{query} AND mediatype:texts' if query.strip() else "mediatype:texts",
        "fl[]": ["identifier", "title", "creator", "language"],
        "rows": limit,
        "start": (page - 1) * limit,
        "output": "json",
    }
    with new_client(timeout=15) as client:
        resp = client.get(SEARCH_URL, params=params)
        resp.raise_for_status()
        docs = resp.json().get("response", {}).get("docs", [])
    return [_to_book(doc) for doc in docs]


def _find_downloadable_file(identifier: str) -> str | None:
    with new_client(timeout=15) as client:
        resp = client.get(f"{METADATA_URL}/{identifier}")
        resp.raise_for_status()
        files = resp.json().get("files", [])

    by_ext: dict[str, str] = {}
    for file_info in files:
        name = file_info.get("name", "")
        for ext in _PREFERRED_EXTENSIONS:
            if name.lower().endswith(ext) and ext not in by_ext:
                by_ext[ext] = name

    for ext in _PREFERRED_EXTENSIONS:
        if ext in by_ext:
            return by_ext[ext]
    return None


def download(book: Book, dest_dir: Path) -> Book:
    identifier = book.id.removeprefix("ia-")
    filename = _find_downloadable_file(identifier)
    if filename is None:
        raise RuntimeError(
            f"'{book.title}' has no downloadable epub/pdf on Internet Archive (borrow-only or scan-only item)"
        )

    dest_dir.mkdir(parents=True, exist_ok=True)
    url = f"{DOWNLOAD_URL}/{identifier}/{quote(filename)}"
    with new_client(timeout=90) as client:
        resp = client.get(url)
        resp.raise_for_status()
        content = resp.content

    ext = filename.rsplit(".", 1)[-1].lower()
    path = dest_dir / f"{safe_filename(book.title)}.{ext}"
    path.write_bytes(content)

    book.format = ext
    book.local_path = str(path)
    book.file_size_bytes = len(content)
    return book


class InternetArchiveSource(BookSource):
    id = "internet_archive"
    name = "Internet Archive"

    def search(self, query: str, limit: int = 20, page: int = 1) -> list[Book]:
        return search(query, limit, page)

    def download(self, book: Book, dest_dir: Path, on_progress=None) -> Book:
        return download(book, dest_dir)
