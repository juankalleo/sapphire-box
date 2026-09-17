"""Local library scan.

Downloaded manga live as folders containing an `index.json` with basic
metadata (id, title, authors, chapters) — this reads that file to build
the in-app library listing.
"""
from __future__ import annotations

import json
from pathlib import Path

from sapphirebox.core.models import Manga

_COVER_NAMES = ("cover.jpg", "cover.png", "cover.webp")


def _find_cover_image(manga_path: Path) -> str | None:
    for name in _COVER_NAMES:
        candidate = manga_path / name
        if candidate.exists():
            return str(candidate)
    return None


def parse_manga_from_index(index_path: Path) -> Manga:
    meta = json.loads(index_path.read_text(encoding="utf-8"))
    local_path = str(index_path.parent)
    chapters = meta.get("chapters", {})
    total_chapters = len(chapters)

    return Manga(
        id=meta["id"],
        title=meta.get("title", index_path.parent.name),
        source_id="local",
        source_name="Biblioteca Local",
        cover_path=_find_cover_image(index_path.parent),
        status=meta.get("state", "unknown"),
        rating=float(meta.get("rating", 0.0)),
        language="pt-BR",
        local_path=local_path,
        total_chapters=total_chapters,
        downloaded_chapters=total_chapters,
    )


def scan_library(library_path: Path) -> list[Manga]:
    if not library_path.exists():
        library_path.mkdir(parents=True, exist_ok=True)
        return []

    results: list[Manga] = []
    # max_depth=2: library_path/<manga>/index.json
    for manga_dir in library_path.iterdir():
        if not manga_dir.is_dir():
            continue
        index_path = manga_dir / "index.json"
        if not index_path.exists():
            continue
        try:
            results.append(parse_manga_from_index(index_path))
        except (json.JSONDecodeError, KeyError, OSError):
            continue

    return results
