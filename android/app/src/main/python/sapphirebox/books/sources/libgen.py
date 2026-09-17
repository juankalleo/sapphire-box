"""Library Genesis (libgen.li) — one of the largest shadow libraries in
the world: millions of books in every language, including a real chunk
in Portuguese (filterable, but the catalog is fundamentally
multi-language — every search result carries its own `language`, shown
back to the user in the listing and on the details/download screen since
results routinely mix languages together).

Unlike eLivros/Dlivros, this mirror's own download chain is plain HTTP
end to end, no ad-gate or CAPTCHA: a search result links to a file
detail page, which links to `/ads.php` (LibGen's own mirror picker, not
a real advertisement wall), which hands back a signed `/get.php` link
that redirects straight to the actual file on their CDN. Verified live —
each hop was fetched and the final one really is the file's bytes.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from sapphirebox.books.sources.base import BookSource, ProgressCallback
from sapphirebox.books.sources.direct_files import clean_text, download_direct_file, parse_size_label
from sapphirebox.core.downloader import new_client
from sapphirebox.core.models import Book, BookFileOption

BASE_URL = "https://libgen.li"
SOURCE_ID = "libgen"
SOURCE_NAME = "Library Genesis"


def _abs(base: str, href: str) -> str:
    return urljoin(base, href)


def _find_results_table(soup: BeautifulSoup):
    for table in soup.find_all("table"):
        if table.select_one("a[href^='edition.php']"):
            return table
    return None


def parse_results(html: str, limit: int) -> list[Book]:
    soup = BeautifulSoup(html, "html.parser")
    table = _find_results_table(soup)
    if table is None or table.find("tbody") is None:
        return []

    books: list[Book] = []
    for row in table.find("tbody").find_all("tr", recursive=False):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 8:
            continue

        title_link = cells[0].select_one("a[href^='edition.php']")
        file_link = cells[6].select_one("a[href^='/file.php']")
        if title_link is None or file_link is None:
            continue

        title = clean_text(title_link.get_text(" ", strip=True))
        if not title:
            continue

        author = clean_text(cells[1].get_text(" ", strip=True)) or None
        language = clean_text(cells[4].get_text(" ", strip=True)) or None
        fmt = clean_text(cells[7].get_text(strip=True)).lower() or "pdf"
        size_bytes = parse_size_label(file_link.get_text(strip=True))

        books.append(
            Book(
                id=_abs(BASE_URL, file_link["href"]),
                title=title,
                author=author,
                source_id=SOURCE_ID,
                source_name=SOURCE_NAME,
                language=language,
                format=fmt,
                file_size_bytes=size_bytes,
            )
        )
        if len(books) >= limit:
            break
    return books


def search(query: str, limit: int = 20, page: int = 1) -> list[Book]:
    q = query.strip()
    if not q:
        return []
    with new_client(timeout=20) as client:
        resp = client.get(f"{BASE_URL}/index.php", params={"req": q, "page": page})
        resp.raise_for_status()
        return parse_results(resp.text, limit)


def _cover_from(soup: BeautifulSoup) -> str | None:
    # Different sub-collections use different prefixes — "/covers/" for
    # one, "/fictioncovers/" for another, and there are likely more —
    # matching the shared "covers/" substring covers all of them instead
    # of enumerating each prefix by hand.
    img = soup.select_one("img[src*='covers/']")
    return _abs(BASE_URL, img["src"]) if img else None


def get_details(book: Book) -> Book:
    with new_client(timeout=20) as client:
        resp = client.get(book.id)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    cover = _cover_from(soup)
    if cover:
        book.cover_path = cover
    return book


def _resolve_direct_url(client: httpx.Client, file_page_url: str) -> tuple[str, str]:
    """Walks file.php -> ads.php -> get.php, the one mirror chain on this
    site that's plain HTTP with no ad-gate/CAPTCHA. Returns
    (direct_download_url, referer_to_use_for_that_request)."""
    resp = client.get(file_page_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    ads_link = soup.select_one('a[href^="/ads.php"]')
    if ads_link is None:
        raise RuntimeError(f"Não encontrei um link de download em {file_page_url}.")
    ads_url = _abs(BASE_URL, ads_link["href"])

    ads_resp = client.get(ads_url, headers={"Referer": file_page_url})
    ads_resp.raise_for_status()
    ads_soup = BeautifulSoup(ads_resp.text, "html.parser")
    get_link = ads_soup.select_one('a[href^="get.php"]')
    if get_link is None:
        raise RuntimeError(f"O mirror não expôs o link de download em {ads_url}.")
    return _abs(ads_url, get_link["href"]), ads_url


def download(book: Book, dest_dir: Path, on_progress: ProgressCallback | None = None) -> Book:
    # Search results don't carry a cover (no thumbnail in that table, and
    # fetching one per row would mean a request per result) — get_details
    # picks it up from the file page before the library shows this as a
    # finished download instead of a blank cover forever.
    book = get_details(book)
    with new_client(timeout=90) as client:
        direct_url, referer = _resolve_direct_url(client, book.id)
        option = BookFileOption(format=book.format or "pdf", url=direct_url, size_bytes=book.file_size_bytes)
        return download_direct_file(client, book, option, dest_dir, on_progress, referer=referer)


class LibGenSource(BookSource):
    id = SOURCE_ID
    name = SOURCE_NAME

    def search(self, query: str, limit: int = 20, page: int = 1) -> list[Book]:
        return search(query, limit, page)

    def get_details(self, book: Book) -> Book:
        return get_details(book)

    def download(self, book: Book, dest_dir: Path, on_progress: ProgressCallback | None = None) -> Book:
        return download(book, dest_dir, on_progress)
