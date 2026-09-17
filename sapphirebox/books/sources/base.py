"""Common interface every book source implements — the books/ counterpart
of manga/sources/base.py."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from sapphirebox.core.models import Book

ProgressCallback = Callable[[int, str], None]


class ManualDownloadRequired(RuntimeError):
    def __init__(self, url: str, message: str) -> None:
        super().__init__(message)
        self.url = url


class BookSource(ABC):
    id: str
    name: str

    @abstractmethod
    def search(self, query: str, limit: int = 20, page: int = 1) -> list[Book]:
        """Sources that don't support paging just ignore `page` and always
        answer with their first page of results."""

    def get_details(self, book: Book) -> Book:
        """Returns richer metadata for a listing item when the source can.

        Older sources only expose enough metadata in search results, so the
        default keeps them compatible with the details screen.
        """
        return book

    @abstractmethod
    def download(self, book: Book, dest_dir: Path, on_progress: ProgressCallback | None = None) -> Book:
        """Downloads `book`'s file into dest_dir and returns it with
        `local_path`/`file_size_bytes` filled in. `on_progress(pct, msg)`
        is optional — most sources finish fast enough not to need it, but
        an ad-gated host like asdocs.net (eLivros/Dlivros) has a genuine
        multi-minute wait, and callers (the web job queue) want to show
        that countdown instead of a frozen progress bar."""
