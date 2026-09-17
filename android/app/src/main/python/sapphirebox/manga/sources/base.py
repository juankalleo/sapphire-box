"""Common interface every manga/manhwa source implements: paginated
search, get_details, and a direct chapter downloader."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from sapphirebox.core.models import Manga, MangaChapterOption

ProgressCallback = Callable[[int, str], None]


class MangaSource(ABC):
    id: str
    name: str

    @abstractmethod
    def search(self, query: str, page: int = 1) -> tuple[list[Manga], int]:
        """Returns (results, total_pages)."""

    @abstractmethod
    def get_details(self, manga_id: str) -> Manga | None:
        ...

    def list_chapters(self, manga_id: str) -> list[MangaChapterOption]:
        return []

    def download_chapters(
        self,
        manga_id: str,
        dest: Path,
        chapters: str,
        fmt: str,
        on_progress: ProgressCallback | None = None,
    ) -> Manga:
        raise NotImplementedError(f"source '{self.id}' has no downloader implemented yet")


def parse_requested_chapters(chapters: str, max_available: int) -> list[int]:
    """Port of commands/download.rs::parse_requested_chapters."""
    raw = chapters.strip()
    if not raw or raw.lower() == "all":
        return list(range(1, max_available + 1))

    out: list[int] = []
    for token in raw.replace(";", ",").split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            a, _, b = token.partition("-")
            try:
                start = int(a.strip())
            except ValueError:
                start = 1
            try:
                end = int(b.strip())
            except ValueError:
                end = start
            lo, hi = max(1, min(start, end)), max(1, min(max(start, end), max(max_available, 1)))
            for n in range(lo, hi + 1):
                if n not in out:
                    out.append(n)
            continue
        try:
            n = max(1, min(int(token), max(max_available, 1)))
        except ValueError:
            continue
        if n not in out:
            out.append(n)

    return sorted(out) if out else [1]


def chapter_number_from_url(url: str, marker: str = "capitulo-") -> float | None:
    """Pulls the numeric chapter id out of a `.../capitulo-12.5` style URL."""
    low = url.lower()
    idx = low.find(marker)
    if idx == -1:
        return None
    tail = low[idx + len(marker) :]
    num = ""
    for ch in tail:
        if ch.isdigit() or ch == ".":
            num += ch
        else:
            break
    if not num:
        return None
    try:
        return float(num)
    except ValueError:
        return None


def chapter_label(url: str, fallback_idx: int, marker: str = "capitulo-") -> tuple[str, str]:
    """Returns (display, file-safe label), e.g. ("12.5", "12_5")."""
    num = chapter_number_from_url(url, marker)
    if num is None:
        return str(fallback_idx), str(fallback_idx)
    display = str(int(num)) if num.is_integer() else f"{num:.3f}".rstrip("0").rstrip(".")
    return display, display.replace(".", "_")
