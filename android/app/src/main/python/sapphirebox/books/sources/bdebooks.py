"""BDeBooks (bdebooks.com/pt) — ebooks PT com links diretos PDF/EPUB."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from sapphirebox.books.sources.base import BookSource, ProgressCallback
from sapphirebox.books.sources.direct_files import (
    clean_text,
    download_direct_file,
    format_size,
    parse_size_label,
    probe_file_size,
    selected_option,
)
from sapphirebox.core.downloader import extract_image_url, new_client
from sapphirebox.core.models import Book, BookFileOption

BASE_URL = "https://bdebooks.com/pt"
SOURCE_ID = "bdebooks"
SOURCE_NAME = "BDeBooks"


def _abs(href: str, base_url: str = BASE_URL) -> str:
    return urljoin(f"{base_url}/", href)


def parse_listing(html: str, limit: int) -> list[Book]:
    soup = BeautifulSoup(html, "html.parser")
    books: list[Book] = []
    seen: set[str] = set()
    for item in soup.select(".ep_book_grid_item_inner"):
        link = item.select_one(".ep_book_grid_item_title a[href]")
        if link is None:
            link = next((a for a in item.select("a[href*='/books/']") if clean_text(a.get_text(" ", strip=True))), None)
        if link is None:
            continue
        href = _abs(link["href"])
        if href in seen:
            continue
        title = clean_text(link.get_text(" ", strip=True))
        if not title:
            continue
        seen.add(href)
        author = clean_text(item.select_one(".bde-card-author").get_text(" ", strip=True) if item.select_one(".bde-card-author") else "")
        books.append(
            Book(
                id=href,
                title=title,
                author=author or None,
                source_id=SOURCE_ID,
                source_name=SOURCE_NAME,
                cover_path=extract_image_url(item),
                language="Português",
                format="pdf",
            )
        )
        if len(books) >= limit:
            break
    return books


def _top_meta(soup: BeautifulSoup) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in soup.select(".ep_single_book_top_meta li"):
        text = clean_text(item.get_text(" ", strip=True))
        if ":" not in text:
            continue
        label, value = text.split(":", 1)
        out[label.lower()] = clean_text(value)
    return out


def _quickfacts(soup: BeautifulSoup) -> tuple[int | None, str | None]:
    facts = [clean_text(node.get_text(" ", strip=True)) for node in soup.select(".bde-quickfacts .bde-qf")]
    pages: int | None = None
    size_label: str | None = None
    for fact in facts:
        if "página" in fact.lower():
            match = re.search(r"\d+", fact)
            if match:
                pages = int(match.group(0))
        if parse_size_label(fact) is not None:
            size_label = fact
    return pages, size_label


def _file_options(soup: BeautifulSoup, referer: str) -> list[BookFileOption]:
    handler = soup.select_one(".ep_pdf_book_link_handler")
    if handler is None:
        return []
    popup_size = clean_text(soup.select_one(".ep_dl_popup_size").get_text(" ", strip=True) if soup.select_one(".ep_dl_popup_size") else "")
    popup_size = popup_size.lstrip("·").strip() or None
    options: list[BookFileOption] = []
    for fmt in ("pdf", "epub", "mobi"):
        url = handler.get(f"data-{fmt}-book-link")
        if not url:
            continue
        option = BookFileOption(
            format=fmt,
            url=url,
            label=fmt.upper(),
            size_bytes=parse_size_label(popup_size),
            size_label=popup_size,
        )
        options.append(option)
    return options


def parse_details(html: str, book: Book) -> Book:
    soup = BeautifulSoup(html, "html.parser")
    meta = _top_meta(soup)
    pages, quick_size = _quickfacts(soup)
    title = clean_text(
        soup.select_one(".ep_single_book_top_title, h1").get_text(" ", strip=True)
        if soup.select_one(".ep_single_book_top_title, h1")
        else book.title
    )
    author = clean_text(
        soup.select_one(".ep_single_book_top_author a, .ep_single_book_top_mb_author a").get_text(" ", strip=True)
        if soup.select_one(".ep_single_book_top_author a, .ep_single_book_top_mb_author a")
        else book.author
    )
    cover_el = soup.select_one('meta[property="og:image"][content]')
    cover = cover_el["content"] if cover_el else extract_image_url(soup)
    synopsis_el = soup.select_one(".ep_single_book_top_content p")
    synopsis = clean_text(synopsis_el.get_text(" ", strip=True) if synopsis_el else book.synopsis)
    options = _file_options(soup, book.id)
    for option in options:
        option.size_label = option.size_label or quick_size
        option.size_bytes = option.size_bytes or parse_size_label(quick_size)
    selected = selected_option(options, book.format)

    return Book(
        id=book.id,
        title=title or book.title,
        author=author or book.author,
        source_id=SOURCE_ID,
        source_name=SOURCE_NAME,
        cover_path=cover or book.cover_path,
        synopsis=synopsis or book.synopsis,
        language=book.language or "Português",
        format=(selected.format if selected else book.format or "pdf"),
        pages=pages or book.pages,
        year=meta.get("primeira publicação") or book.year,
        category=meta.get("gênero") or meta.get("genero") or book.category,
        file_size_bytes=(selected.size_bytes if selected else book.file_size_bytes),
        file_options=options,
    )


def search(query: str, limit: int = 20, page: int = 1) -> list[Book]:
    if query.strip():
        path = "/" if page <= 1 else f"/page/{page}/"
        params = {"s": query.strip(), "post_type": "book"}
    else:
        path = "/catalogo-de-ebooks/" if page <= 1 else f"/catalogo-de-ebooks/page/{page}/"
        params = {}
    with new_client(timeout=20) as client:
        resp = client.get(f"{BASE_URL}{path}", params=params)
        resp.raise_for_status()
        return parse_listing(resp.text, limit)


def get_details(book: Book) -> Book:
    with new_client(timeout=30) as client:
        resp = client.get(book.id)
        resp.raise_for_status()
        detailed = parse_details(resp.text, book)
        for option in detailed.file_options:
            probed = probe_file_size(client, option.url, referer=book.id)
            if probed:
                option.size_bytes = probed
                option.size_label = format_size(probed)
        selected = selected_option(detailed.file_options, book.format)
        if selected:
            detailed.format = selected.format
            detailed.file_size_bytes = selected.size_bytes
        return detailed


def download(book: Book, dest_dir: Path, on_progress: ProgressCallback | None = None) -> Book:
    detailed = get_details(book)
    option = selected_option(detailed.file_options, book.format)
    if option is None:
        raise RuntimeError(f"Não encontrei um arquivo direto em {book.id}.")
    with new_client(timeout=120) as client:
        return download_direct_file(client, detailed, option, dest_dir, on_progress, referer=book.id)


class BDeBooksSource(BookSource):
    id = SOURCE_ID
    name = SOURCE_NAME

    def search(self, query: str, limit: int = 20, page: int = 1) -> list[Book]:
        return search(query, limit, page)

    def get_details(self, book: Book) -> Book:
        return get_details(book)

    def download(self, book: Book, dest_dir: Path, on_progress: ProgressCallback | None = None) -> Book:
        return download(book, dest_dir, on_progress)
