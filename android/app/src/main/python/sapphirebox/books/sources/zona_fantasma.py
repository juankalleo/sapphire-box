"""Zona Fantasma (zonafantasmanet.com.br) — WordPress simples, um post por
edição/número de HQ. Busca, navegação sem termo (`?s=` vazio devolve o
catálogo inteiro) e paginação (`/page/N/`) usam a mesma marcação padrão do
tema (`article.post`), então um único parser cobre os três casos.

O arquivo em si fica atrás do Mediafire — mas, diferente do
eLivros/Dlivros (asdocs.net, com timer/anúncio), o Mediafire expõe o link
direto do arquivo no próprio HTML da página (`#downloadButton`), então dá
pra automatizar o download de verdade, sem navegador.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from sapphirebox.core.downloader import new_client, safe_filename
from sapphirebox.core.models import Book
from sapphirebox.books.sources.base import BookSource

BASE_URL = "https://zonafantasmanet.com.br"


def _parse_listing(html: str, limit: int) -> list[Book]:
    soup = BeautifulSoup(html, "html.parser")
    books: list[Book] = []
    for article in soup.select("article.post"):
        link = article.select_one("h2.entry-title a[href]")
        if link is None:
            continue
        title = link.get_text(strip=True)
        if not title:
            continue
        img = article.select_one("img[src]")
        cover = img["src"] if img else None
        books.append(
            Book(
                id=link["href"],
                title=title,
                source_id="zonafantasma",
                source_name="Zona Fantasma",
                cover_path=cover,
                language="Português",
                format="cbr",
            )
        )
        if len(books) >= limit:
            break
    return books


def search(query: str, limit: int = 20, page: int = 1) -> list[Book]:
    path = "/" if page <= 1 else f"/page/{page}/"
    with new_client(timeout=15) as client:
        resp = client.get(f"{BASE_URL}{path}", params={"s": query.strip()})
        resp.raise_for_status()
        html = resp.text
    return _parse_listing(html, limit)


def _find_mediafire_link(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href]"):
        href = a["href"]
        if "mediafire.com" in href:
            return href
    return None


def download(book: Book, dest_dir: Path) -> Book:
    with new_client(timeout=20) as client:
        resp = client.get(book.id)
        resp.raise_for_status()
        mediafire_url = _find_mediafire_link(resp.text)
        if mediafire_url is None:
            raise RuntimeError(
                f"Não encontrei um link de download automatizável em {book.id} — abra a página e baixe manualmente."
            )

        mf_resp = client.get(mediafire_url)
        mf_resp.raise_for_status()
        mf_soup = BeautifulSoup(mf_resp.text, "html.parser")
        download_btn = mf_soup.select_one("a#downloadButton[href]")
        if download_btn is None:
            raise RuntimeError(
                f"O Mediafire não liberou o link direto pra esse arquivo — abra {mediafire_url} e baixe manualmente."
            )
        file_url = download_btn["href"]

        dest_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(urlparse(file_url).path).suffix.lstrip(".") or book.format
        path = dest_dir / f"{safe_filename(book.title)}.{ext}"
        size = 0
        with client.stream("GET", file_url) as file_resp:
            file_resp.raise_for_status()
            with open(path, "wb") as f:
                for chunk in file_resp.iter_bytes():
                    f.write(chunk)
                    size += len(chunk)

    book.format = ext
    book.local_path = str(path)
    book.file_size_bytes = size
    return book


class ZonaFantasmaSource(BookSource):
    id = "zonafantasma"
    name = "Zona Fantasma"

    def search(self, query: str, limit: int = 20, page: int = 1) -> list[Book]:
        return search(query, limit, page)

    def download(self, book: Book, dest_dir: Path, on_progress=None) -> Book:
        return download(book, dest_dir)
