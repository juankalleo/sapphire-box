"""Multiverso HQ (multiversohq.com) — agregador de HQs organizado por
editora/personagem. Busca, navegação sem termo (`?s=` vazio devolve o
catálogo inteiro, milhares de itens) e paginação (`/page/N/?s=...`) usam a
marcação do tema (`ul.videos > li`, reaproveitada de um template de
fotos/vídeos).

O arquivo em si fica atrás do Workupload, que — diferente do Mediafire
usado pela Zona Fantasma — só libera o link depois de resolver um desafio
JS (puzzle SHA-256 tipo prova-de-trabalho) pra confirmar que não é um
robô. Não dá pra automatizar isso com HTTP simples sem contornar uma
proteção anti-bot de propósito, então `download` aqui é honesto: devolve
onde terminar manualmente, como já fazemos pro eLivros/Dlivros.
"""
from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from sapphirebox.core.downloader import new_client
from sapphirebox.core.models import Book
from sapphirebox.books.sources.base import BookSource, ManualDownloadRequired

BASE_URL = "https://multiversohq.com"


def _parse_listing(html: str, limit: int) -> list[Book]:
    soup = BeautifulSoup(html, "html.parser")
    books: list[Book] = []
    for li in soup.select("ul.videos > li"):
        link = li.select_one("a.titulo[href]") or li.select_one(".thumb-conteudo a[href]")
        if link is None:
            continue
        title_el = li.select_one("a.titulo h2")
        title = title_el.get_text(strip=True) if title_el else (link.get("title") or "").strip()
        if not title:
            continue
        img = li.select_one("img.thumb[src]")
        cover = img["src"] if img else None
        books.append(
            Book(
                id=link["href"],
                title=title,
                source_id="multiversohq",
                source_name="Multiverso HQ",
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


def _find_download_link(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href]"):
        href = a["href"]
        if href.startswith("http") and "multiversohq.com" not in href:
            return href
    return None


def download(book: Book, dest_dir: Path) -> Book:
    with new_client(timeout=20) as client:
        resp = client.get(book.id)
        resp.raise_for_status()
        link = _find_download_link(resp.text)

    where = link or book.id
    raise ManualDownloadRequired(
        where,
        "Multiverso HQ envia esse arquivo para o Workupload, que exige uma checagem anti-robô em navegador real. "
        "Abra no navegador, finalize o download e depois importe o arquivo baixado pela fila.",
    )


class MultiversoHQSource(BookSource):
    id = "multiversohq"
    name = "Multiverso HQ"

    def search(self, query: str, limit: int = 20, page: int = 1) -> list[Book]:
        return search(query, limit, page)

    def download(self, book: Book, dest_dir: Path, on_progress=None) -> Book:
        return download(book, dest_dir)
