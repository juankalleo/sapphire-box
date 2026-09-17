"""Loads the bundled books source catalog and wires implemented sources."""
from __future__ import annotations

import json
from dataclasses import dataclass

from sapphirebox.books.sources.baixelivros import BaixeLivrosSource
from sapphirebox.books.sources.base import BookSource
from sapphirebox.books.sources.bdebooks import BDeBooksSource
from sapphirebox.books.sources.gutenberg import GutenbergSource
from sapphirebox.books.sources.internet_archive import InternetArchiveSource
from sapphirebox.books.sources.libgen import LibGenSource
from sapphirebox.books.sources.multiverso_hq import MultiversoHQSource
from sapphirebox.books.sources.zona_fantasma import ZonaFantasmaSource
from sapphirebox.core.resources import read_text_resource

_IMPLEMENTED: dict[str, type[BookSource]] = {
    "baixelivros": BaixeLivrosSource,
    "bdebooks": BDeBooksSource,
    "libgen": LibGenSource,
    "gutenberg": GutenbergSource,
    "internet_archive": InternetArchiveSource,
    "zonafantasma": ZonaFantasmaSource,
    "multiversohq": MultiversoHQSource,
}


@dataclass
class BookSourceInfo:
    id: str
    name: str
    url: str
    category: str
    language: str
    formats: list[str]
    enabled: bool
    priority: int
    description: str | None = None

    @property
    def has_python_source(self) -> bool:
        return self.id in _IMPLEMENTED


def load_source_infos() -> list[BookSourceInfo]:
    raw = json.loads(read_text_resource("data", "sources_books.json"))
    return [
        BookSourceInfo(
            id=item["id"],
            name=item["name"],
            url=item["url"],
            category=item.get("category", "livro"),
            language=item.get("language", ""),
            formats=item.get("formats", []),
            enabled=item.get("enabled", False),
            priority=item.get("priority", 999),
            description=item.get("description"),
        )
        for item in raw
    ]


def list_enabled(category: str | None = None) -> list[BookSourceInfo]:
    infos = (s for s in load_source_infos() if s.enabled and s.id in _IMPLEMENTED)
    if category:
        infos = (s for s in infos if s.category == category)
    return sorted(infos, key=lambda s: s.priority)


def get_source(source_id: str) -> BookSource | None:
    cls = _IMPLEMENTED.get(source_id)
    return cls() if cls else None


def get_source_category(source_id: str) -> str | None:
    """"livro" or "quadrinho" for a known source — used to sort a
    downloaded item into the right library shelf, since a book's own
    scraped Book.category is really its genre (e.g. "Romance"), not this
    livro/quadrinho split."""
    for info in load_source_infos():
        if info.id == source_id:
            return info.category
    return None


@dataclass
class DocumentSourceInfo:
    """A cataloged-but-not-yet-wired-up source for the Fase 2 generic
    engine (see the bundled sources_documents.json) — books and comics (PT-BR
    focused) that were actually checked live before being listed here."""

    id: str
    name: str
    url: str
    category: str
    language: str
    formats: list[str]
    renderer: str
    enabled: bool
    priority: int
    description: str | None = None
    note: str | None = None


def load_document_catalog() -> list[DocumentSourceInfo]:
    raw = json.loads(read_text_resource("data", "sources_documents.json"))
    return sorted(
        (
            DocumentSourceInfo(
                id=item["id"],
                name=item["name"],
                url=item["url"],
                category=item.get("category", ""),
                language=item.get("language", ""),
                formats=item.get("formats", []),
                renderer=item.get("renderer", "http"),
                enabled=item.get("enabled", False),
                priority=item.get("priority", 999),
                description=item.get("description"),
                note=item.get("note"),
            )
            for item in raw
        ),
        key=lambda s: s.priority,
    )
