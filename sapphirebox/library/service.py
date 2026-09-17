"""Thin orchestration between the folder scan and the SQLite cache.

Favorites, reading progress and the settings key/value store are ported
in Phase 1 (see the Sapphire Box plan artifact) — this only covers what the
Phase 0 CLI needs: syncing what's on disk into the `manga` table and
listing it back out.
"""
from __future__ import annotations

from pathlib import Path

from sapphirebox.core.models import Manga
from sapphirebox.library import repository
from sapphirebox.manga import library as manga_library


def sync_local_library(library_path: Path) -> list[Manga]:
    scanned = manga_library.scan_library(library_path)
    for manga in scanned:
        repository.upsert_manga(manga)
    return scanned


def list_library(page: int = 1, page_size: int = 20) -> tuple[list[Manga], int]:
    return repository.list_library(page, page_size)
