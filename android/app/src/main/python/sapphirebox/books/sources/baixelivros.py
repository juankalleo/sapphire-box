"""Baixe Livros (baixelivros.com.br) — catalogo PT-BR com PDFs diretos."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

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

BASE_URL = "https://www.baixelivros.com.br"
SOURCE_ID = "baixelivros"
SOURCE_NAME = "Baixe Livros"

_DOWNLOAD_URL_RE = re.compile(r"downloadSimple\(['\"]([^'\"]+)['\"]\)")


def _abs(href: str, base_url: str = BASE_URL) -> str:
    return urljoin(base_url, href)


def _split_title_author(raw: str) -> tuple[str, str | None]:
    text = clean_text(raw)
    for sep in (" – ", " - "):
        if sep in text:
            title, author = text.split(sep, 1)
            return clean_text(title), clean_text(author) or None
    return text, None


def _cover_from(node, soup: BeautifulSoup | None = None) -> str | None:
    og = soup.select_one('meta[property="og:image"][content]') if soup else None
    if og:
        return _abs(og["content"])
    for candidate in node.select("[data-src], img[src], source[srcset], [style]"):
        for attr in ("data-src", "src", "srcset", "data-srcset", "style"):
            value = candidate.get(attr)
            if value:
                if attr.endswith("srcset"):
                    value = value.split(",", 1)[0].split()[0]
                if value:
                    return _abs(value)
    return extract_image_url(node)


def parse_listing(html: str, limit: int) -> list[Book]:
    soup = BeautifulSoup(html, "html.parser")
    books: list[Book] = []
    seen: set[str] = set()
    for item in soup.select(".item-inner, article"):
        link = item.select_one("a.post-title[href], h2.title a[href]")
        if link is None:
            continue
        href = _abs(link["href"])
        if href in seen:
            continue
        title, author = _split_title_author(link.get_text(" ", strip=True) or link.get("title", ""))
        if not title:
            continue
        seen.add(href)
        books.append(
            Book(
                id=href,
                title=title,
                author=author,
                source_id=SOURCE_ID,
                source_name=SOURCE_NAME,
                cover_path=_cover_from(item),
                language="Português",
                format="pdf",
            )
        )
        if len(books) >= limit:
            break
    return books


def _metadata(soup: BeautifulSoup) -> dict[str, str]:
    out: dict[str, str] = {}
    for card in soup.select(".bltm-detalhe-card"):
        label = clean_text(card.select_one("dt").get_text(" ", strip=True) if card.select_one("dt") else "")
        value = clean_text(card.select_one("dd").get_text(" ", strip=True) if card.select_one("dd") else "")
        if label and value:
            out[label.lower()] = value
    return out


def _download_target(anchor) -> str | None:
    target = anchor.get("data-target")
    if target:
        return target
    href = anchor.get("href") or ""
    params = parse_qs(urlparse(_abs(href)).query)
    for key in ("pdf", "epub", "mobi"):
        if params.get(key):
            return params[key][0]
    onclick = anchor.get("onclick") or ""
    match = _DOWNLOAD_URL_RE.search(onclick)
    return match.group(1) if match else None


def _file_options(soup: BeautifulSoup, meta: dict[str, str]) -> list[BookFileOption]:
    options: list[BookFileOption] = []
    seen: set[str] = set()
    size_label = meta.get("tamanho do arquivo")
    size_bytes = parse_size_label(size_label)
    for anchor in soup.select("a.bltm-acao-download[href], a[href*='download-gratuito'], a[data-target]"):
        url = _download_target(anchor)
        if not url or url in seen:
            continue
        seen.add(url)
        parsed_path = urlparse(url).path.lower()
        fmt = "pdf"
        for candidate in ("pdf", "epub", "mobi", "txt"):
            if parsed_path.endswith(f".{candidate}"):
                fmt = candidate
                break
        options.append(
            BookFileOption(
                format=fmt,
                url=url,
                label=fmt.upper(),
                size_bytes=size_bytes,
                size_label=size_label,
            )
        )
    return options


def parse_details(html: str, book: Book) -> Book:
    soup = BeautifulSoup(html, "html.parser")
    meta = _metadata(soup)
    title = clean_text(soup.select_one("#bltm-titulo, h1").get_text(" ", strip=True) if soup.select_one("#bltm-titulo, h1") else book.title)
    author = clean_text(
        soup.select_one(".bltm-autor-nome").get_text(" ", strip=True) if soup.select_one(".bltm-autor-nome") else book.author
    )
    synopsis_el = soup.select_one(".bltm-resumo")
    if synopsis_el:
        heading = synopsis_el.select_one("h1, h2, h3")
        if heading:
            heading.decompose()
    synopsis = clean_text(synopsis_el.get_text(" ", strip=True) if synopsis_el else book.synopsis)
    pages_raw = meta.get("páginas") or meta.get("paginas")
    pages_match = re.search(r"\d+", pages_raw or "")
    options = _file_options(soup, meta)
    cover = _cover_from(soup, soup)

    selected = selected_option(options, book.format)
    if selected and selected.size_bytes is None:
        selected.size_bytes = parse_size_label(selected.size_label)
        selected.size_label = selected.size_label or format_size(selected.size_bytes)

    return Book(
        id=book.id,
        title=title or book.title,
        author=author or book.author,
        source_id=SOURCE_ID,
        source_name=SOURCE_NAME,
        cover_path=cover or book.cover_path,
        synopsis=synopsis or book.synopsis,
        language=meta.get("idioma") or book.language or "Português",
        format=(selected.format if selected else book.format or "pdf"),
        pages=int(pages_match.group(0)) if pages_match else book.pages,
        year=meta.get("ano") or book.year,
        category=meta.get("tipo") or book.category,
        file_size_bytes=(selected.size_bytes if selected else book.file_size_bytes),
        file_options=options,
    )


def search(query: str, limit: int = 20, page: int = 1) -> list[Book]:
    path = "/" if page <= 1 else f"/page/{page}/"
    params = {"s": query.strip()} if query.strip() else {}
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
            if option.size_bytes is None:
                option.size_bytes = probe_file_size(client, option.url, referer=book.id)
                option.size_label = option.size_label or format_size(option.size_bytes)
        return detailed


def download(book: Book, dest_dir: Path, on_progress: ProgressCallback | None = None) -> Book:
    detailed = get_details(book)
    option = selected_option(detailed.file_options, book.format)
    if option is None:
        raise RuntimeError(f"Não encontrei um arquivo direto em {book.id}.")
    with new_client(timeout=120) as client:
        return download_direct_file(client, detailed, option, dest_dir, on_progress, referer=book.id)


class BaixeLivrosSource(BookSource):
    id = SOURCE_ID
    name = SOURCE_NAME

    def search(self, query: str, limit: int = 20, page: int = 1) -> list[Book]:
        return search(query, limit, page)

    def get_details(self, book: Book) -> Book:
        return get_details(book)

    def download(self, book: Book, dest_dir: Path, on_progress: ProgressCallback | None = None) -> Book:
        return download(book, dest_dir, on_progress)
