"""Wires manga/books downloads into the background job registry
(core/worker.py) so the web UI can start a download and poll its
progress instead of blocking on one HTTP request until it's done.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

from sapphirebox.books import manager as books_manager
from sapphirebox.books.sources.base import ManualDownloadRequired
from sapphirebox.core import config
from sapphirebox.core import worker
from sapphirebox.core.downloader import safe_filename
from sapphirebox.core.models import Book, DownloadJob
from sapphirebox.library import repository
from sapphirebox.manga import manager as manga_manager

_MANUAL_EXTS = {
    "cbr": {".cbr", ".cbz", ".rar", ".zip"},
    "cbz": {".cbz", ".cbr", ".zip", ".rar"},
    "pdf": {".pdf"},
    "epub": {".epub"},
    "mobi": {".mobi", ".azw3"},
}


def start_manga_download(
    source_id: str,
    manga_id: str,
    title: str | None,
    cover_path: str | None,
    chapters: str,
    fmt: str,
    source_name: str | None = None,
) -> DownloadJob:
    job = worker.new_job()
    worker.update(
        job.id,
        title=title or manga_id,
        cover_path=cover_path,
        domain="manga",
        source_id=source_id,
        source_name=source_name or source_id,
        item_id=manga_id,
        chapters=chapters,
        format=fmt,
    )

    def on_progress(pct: int, msg: str) -> None:
        if worker.is_cancel_requested(job.id):
            raise worker.DownloadCancelled()
        worker.update(job.id, progress=pct, last_stdout=msg)

    def run() -> None:
        manga = manga_manager.download(source_id, manga_id, chapters, fmt, on_progress=on_progress, title=title)
        worker.update(
            job.id,
            status="completed",
            progress=100,
            title=manga.title,
            cover_path=manga.cover_path,
            dest=manga.local_path,
            source_id=manga.source_id,
            source_name=manga.source_name,
            item_id=manga.id,
        )

    worker.run_in_background(job, run)
    return job


def start_book_download(
    source_id: str,
    book_id: str,
    title: str,
    source_name: str,
    author: str | None,
    cover_path: str | None,
    fmt: str,
) -> DownloadJob:
    job = worker.new_job()
    worker.update(
        job.id,
        title=title,
        cover_path=cover_path,
        domain="book",
        source_id=source_id,
        item_id=book_id,
        format=fmt,
        author=author,
        source_name=source_name,
    )

    def on_progress(pct: int, msg: str) -> None:
        if worker.is_cancel_requested(job.id):
            raise worker.DownloadCancelled()
        worker.update(job.id, progress=pct, last_stdout=msg)

    def run() -> None:
        worker.update(job.id, progress=1, last_stdout="Baixando…")
        stub = Book(
            id=book_id,
            title=title,
            source_id=source_id,
            source_name=source_name,
            author=author,
            cover_path=cover_path,
            format=fmt or "epub",
        )
        try:
            book = books_manager.download(stub, on_progress=on_progress)
        except ManualDownloadRequired as exc:
            worker.update(
                job.id,
                status="manual_required",
                progress=100,
                manual_url=exc.url,
                last_stdout=str(exc),
            )
            return
        worker.update(
            job.id,
            status="completed",
            progress=100,
            title=book.title,
            cover_path=book.cover_path,
            dest=book.local_path,
            item_id=book.id,
            source_id=book.source_id,
            source_name=book.source_name,
            author=book.author,
            format=book.format,
        )

    worker.run_in_background(job, run)
    return job


def open_manual_download(job: DownloadJob) -> None:
    url = (job.manual_url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("Esse download não tem um link manual válido")
    if sys.platform == "darwin":
        for browser_name in ("Google Chrome", "Chromium"):
            if Path(f"/Applications/{browser_name}.app").exists():
                subprocess.Popen(["open", "-a", browser_name, url])
                return
    webbrowser.open(url)


def _manual_download_candidates(job: DownloadJob) -> list[Path]:
    downloads_dir = Path.home() / "Downloads"
    if not downloads_dir.exists():
        return []
    wanted = _MANUAL_EXTS.get((job.format or "").lower(), {".cbr", ".cbz", ".pdf", ".epub", ".mobi", ".azw3"})
    candidates = [
        path
        for path in downloads_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in wanted
        and not path.name.endswith((".crdownload", ".download", ".part"))
    ]
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)


def import_latest_manual_download(job: DownloadJob) -> Book:
    if job.status != "manual_required" or job.domain != "book":
        raise RuntimeError("Esse job não está aguardando importação manual")
    candidates = _manual_download_candidates(job)
    if not candidates:
        raise FileNotFoundError("Não encontrei um arquivo compatível na pasta Downloads")

    source = candidates[0]
    dest_dir = config.get_books_library_path()
    dest_dir.mkdir(parents=True, exist_ok=True)
    title = job.title or source.stem
    suffix = source.suffix.lower()
    dest = dest_dir / f"{safe_filename(title, fallback=source.stem)}{suffix}"
    counter = 2
    while dest.exists():
        dest = dest_dir / f"{safe_filename(title, fallback=source.stem)}-{counter}{suffix}"
        counter += 1
    shutil.move(str(source), str(dest))

    book = Book(
        id=job.item_id or job.manual_url or str(dest),
        title=title,
        source_id=job.source_id or "manual",
        source_name=job.source_name or job.source_id or "Manual",
        author=job.author,
        cover_path=job.cover_path,
        format=suffix.lstrip("."),
        local_path=str(dest),
        file_size_bytes=dest.stat().st_size,
    )
    repository.upsert_book(book)
    worker.update(
        job.id,
        status="completed",
        progress=100,
        dest=str(dest),
        format=book.format,
        last_stdout=f"Arquivo importado de Downloads: {dest.name}",
        error=None,
    )
    return book


def retry_job(job: DownloadJob) -> DownloadJob | None:
    """Starts a brand-new job from a finished (completed/cancelled/error)
    one's stored request — used by the "tentar de novo" button, since the
    original job's own thread is long gone."""
    if job.domain == "manga":
        return start_manga_download(
            job.source_id, job.item_id, job.title, job.cover_path, job.chapters, job.format, job.source_name
        )
    if job.domain == "book":
        return start_book_download(
            job.source_id, job.item_id, job.title, job.source_name, job.author, job.cover_path, job.format
        )
    return None
