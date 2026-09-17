"""Loads the bundled manga source catalog and wires implemented sources.

Entries without a Python implementation are listed but inert until a
scraper for them is written (see manga/sources/base.py).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from sapphirebox.core.resources import read_text_resource
from sapphirebox.manga.sources.base import MangaSource
from sapphirebox.manga.sources.mangalivre import MangaLivreSource
from sapphirebox.manga.sources.niadd import NiaddSource

_IMPLEMENTED: dict[str, type[MangaSource]] = {
    "mangalivre": MangaLivreSource,
    "niadd": NiaddSource,
}


@dataclass
class SourceInfo:
    id: str
    name: str
    url: str
    language: str
    region: str
    enabled: bool
    priority: int
    description: str | None = None

    @property
    def has_python_source(self) -> bool:
        return self.id in _IMPLEMENTED


def load_source_infos() -> list[SourceInfo]:
    raw = json.loads(read_text_resource("data", "sources_manga.json"))
    return [
        SourceInfo(
            id=item["id"],
            name=item["name"],
            url=item["url"],
            language=item.get("language", ""),
            region=item.get("region", ""),
            enabled=item.get("enabled", False),
            priority=item.get("priority", 999),
            description=item.get("description"),
        )
        for item in raw
    ]


def list_enabled() -> list[SourceInfo]:
    return sorted((s for s in load_source_infos() if s.enabled), key=lambda s: s.priority)


def get_source(source_id: str) -> MangaSource | None:
    cls = _IMPLEMENTED.get(source_id)
    return cls() if cls else None
