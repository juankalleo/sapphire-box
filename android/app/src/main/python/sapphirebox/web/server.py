"""Local web preview for Sapphire Box.

A thin FastAPI layer over the same manager functions the CLI already
uses, serving the bundled static frontend at `/`. This exists so the
app's look and feel can be tested in a browser — it is not the Fase 1
API (favorites/progress, versioned routes, etc.), just enough surface
for search + a unified library + basic settings.
"""
from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query, Response
from fastapi.staticfiles import StaticFiles

from sapphirebox.books import manager as books_manager
from sapphirebox.books.sources import registry as books_registry
from sapphirebox.core import config, worker
from sapphirebox.core.models import Book, DownloadJob, Manga
from sapphirebox.core.resources import resource_path
from sapphirebox.library import repository
from sapphirebox.manga import manager as manga_manager
from sapphirebox.manga.sources import registry as manga_registry
from sapphirebox.web import downloads as downloads_service
from sapphirebox.web import reader as reader_service

_WEB_DIR = resource_path("web")
_FAVICON_DIR = _WEB_DIR / "assets" / "favicons"

app = FastAPI(title="Sapphire Box")


def _remove_download_path(path_value: str | None) -> bool:
    if not path_value:
        return False
    path = Path(path_value)
    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
            return True
        if path.is_dir():
            shutil.rmtree(path)
            return True
    except FileNotFoundError:
        return False
    return False


def _clear_directory_contents(root: Path) -> int:
    root.mkdir(parents=True, exist_ok=True)
    removed = 0
    for child in root.iterdir():
        removed += 1 if _remove_download_path(str(child)) else 0
    return removed


def _favicon_path(source_id: str) -> str | None:
    for suffix in (".png", ".ico", ".svg"):
        if (_FAVICON_DIR / f"{source_id}{suffix}").exists():
            return f"/assets/favicons/{source_id}{suffix}"
    return None


def _manga_dict(m: Manga) -> dict:
    chapter_options = [
        {
            "index": chapter.index,
            "label": chapter.label,
            "downloaded": chapter.downloaded,
        }
        for chapter in m.chapter_options
    ]
    return {
        "kind": "manga",
        "id": m.id,
        "title": m.title,
        "sourceId": m.source_id,
        "sourceName": m.source_name,
        "coverPath": m.cover_path,
        "synopsis": m.synopsis,
        "status": m.status,
        "totalChapters": m.total_chapters,
        "downloadedChapters": m.downloaded_chapters,
        "localPath": m.local_path,
        "lastUpdated": m.last_updated,
        "chapterOptions": chapter_options,
    }


def _book_dict(b: Book) -> dict:
    file_options = [
        {
            "format": option.format,
            "label": option.label or option.format.upper(),
            "sizeBytes": option.size_bytes,
            "sizeLabel": option.size_label,
        }
        for option in b.file_options
    ]
    return {
        "kind": "book",
        "id": b.id,
        "title": b.title,
        "author": b.author,
        "sourceId": b.source_id,
        "sourceName": b.source_name,
        "coverPath": b.cover_path,
        "language": b.language,
        "format": b.format,
        "pages": b.pages,
        "year": b.year,
        "category": b.category,
        "sourceCategory": books_registry.get_source_category(b.source_id),
        "synopsis": b.synopsis,
        "fileSizeBytes": b.file_size_bytes,
        "fileOptions": file_options,
        "localPath": b.local_path,
        "lastUpdated": b.last_updated,
    }


def _job_dict(job: DownloadJob) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "title": job.title,
        "coverPath": job.cover_path,
        "dest": job.dest,
        "lastStdout": job.last_stdout,
        "error": job.error,
        "domain": job.domain,
        "sourceId": job.source_id,
        "sourceName": job.source_name,
        "itemId": job.item_id,
        "author": job.author,
        "format": job.format,
        "chapters": job.chapters,
        "manualUrl": job.manual_url,
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# --- descobrir (catálogo unificado de fontes navegáveis) -------------------

@app.get("/api/sources")
def all_sources() -> list[dict]:
    out: list[dict] = []
    for s in manga_registry.list_enabled():
        if not s.has_python_source:
            continue
        out.append({
            "id": s.id,
            "name": s.name,
            "domain": "manga",
            "category": "manga",
            "language": s.language,
            "url": s.url,
            "faviconPath": _favicon_path(s.id),
        })
    for s in books_registry.list_enabled():
        out.append({
            "id": s.id,
            "name": s.name,
            "domain": "books",
            "category": s.category,
            "language": s.language,
            "url": s.url,
            "faviconPath": _favicon_path(s.id),
        })
    return out


# --- manga -------------------------------------------------------------

@app.get("/api/manga/sources")
def manga_sources() -> list[dict]:
    return [
        {
            "id": s.id,
            "name": s.name,
            "language": s.language,
            "priority": s.priority,
            "implemented": s.has_python_source,
        }
        for s in manga_registry.load_source_infos()
    ]


@app.get("/api/manga/search")
def manga_search(q: str = Query(...), source: str = "", page: int = 1) -> dict:
    try:
        if source:
            results, total_pages = manga_manager.search_web(source, q, page)
        else:
            results, total_pages = manga_manager.search_all(q), 1
    except Exception as exc:  # live scraping — surface as a normal API error, not a 500 traceback
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"results": [_manga_dict(m) for m in results], "totalPages": total_pages}


@app.get("/api/manga/details")
def manga_details(
    source: str = Query(...),
    manga_id: str = Query(..., alias="id"),
    title: str | None = None,
    cover_path: str | None = Query(None, alias="coverPath"),
) -> dict:
    try:
        manga = manga_manager.get_details(source, manga_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if manga is None:
        manga = Manga(id=manga_id, title=title or manga_id, source_id=source, source_name=source, cover_path=cover_path)
    return _manga_dict(manga)


@app.get("/api/manga/chapter-options")
def manga_chapter_options(source: str = Query(...), manga_id: str = Query(..., alias="id")) -> dict:
    try:
        chapters = manga_manager.list_chapters(source, manga_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "chapters": [
            {"index": chapter.index, "label": chapter.label, "downloaded": chapter.downloaded}
            for chapter in chapters
        ]
    }


@app.post("/api/manga/download")
def manga_download(payload: dict = Body(...)) -> dict:
    source_id = payload.get("sourceId")
    manga_id = payload.get("mangaId")
    if not source_id or not manga_id:
        raise HTTPException(status_code=400, detail="sourceId e mangaId são obrigatórios")
    job = downloads_service.start_manga_download(
        source_id,
        manga_id,
        payload.get("title"),
        payload.get("coverPath"),
        payload.get("chapters", "all"),
        payload.get("format", "cbz"),
        payload.get("sourceName"),
    )
    return _job_dict(job)


# --- books ---------------------------------------------------------------

@app.get("/api/books/sources")
def books_sources(category: str | None = None) -> list[dict]:
    implemented = [
        {"id": s.id, "name": s.name, "category": s.category, "formats": s.formats, "implemented": True}
        for s in books_registry.list_enabled(category)
    ]
    catalog = [
        {"id": s.id, "name": s.name, "category": s.category, "formats": s.formats, "implemented": False}
        for s in books_registry.load_document_catalog()
        if category is None or s.category == category
    ]
    return implemented + catalog


@app.get("/api/books/search")
def books_search(
    q: str = Query(...),
    source: str | None = None,
    category: str | None = None,
    limit: int = 20,
    page: int = 1,
) -> dict:
    try:
        results, total_pages = books_manager.search(q, source, limit, category, page)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"results": [_book_dict(b) for b in results], "totalPages": total_pages}


@app.get("/api/books/details")
def book_details(
    source: str = Query(...),
    book_id: str = Query(..., alias="id"),
    title: str | None = None,
    source_name: str | None = Query(None, alias="sourceName"),
    author: str | None = None,
    cover_path: str | None = Query(None, alias="coverPath"),
    fmt: str | None = Query(None, alias="format"),
) -> dict:
    try:
        book = books_manager.get_details(
            Book(
                id=book_id,
                title=title or book_id,
                source_id=source,
                source_name=source_name or source,
                author=author,
                cover_path=cover_path,
                format=fmt or "pdf",
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _book_dict(book)


@app.post("/api/books/download")
def book_download(payload: dict = Body(...)) -> dict:
    book_id = payload.get("bookId")
    if not book_id or not payload.get("title") or not payload.get("sourceId"):
        raise HTTPException(status_code=400, detail="bookId, title e sourceId são obrigatórios")
    job = downloads_service.start_book_download(
        payload["sourceId"],
        book_id,
        payload["title"],
        payload.get("sourceName", payload["sourceId"]),
        payload.get("author"),
        payload.get("coverPath"),
        payload.get("format", "epub"),
    )
    return _job_dict(job)


# --- jobs (progresso dos downloads em andamento) ---------------------------

@app.get("/api/jobs")
def list_jobs() -> dict:
    jobs = sorted(worker.snapshot(), key=lambda j: j.id)
    return {"jobs": [_job_dict(j) for j in jobs]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = worker.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job não encontrado")
    return _job_dict(job)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    if not worker.request_cancel(job_id):
        raise HTTPException(status_code=404, detail="job não encontrado ou já não está mais em andamento")
    return {"ok": True}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    if not worker.delete(job_id):
        raise HTTPException(status_code=404, detail="job não encontrado")
    return {"ok": True}


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str) -> dict:
    job = worker.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job não encontrado")
    new_job = downloads_service.retry_job(job)
    if new_job is None:
        raise HTTPException(status_code=400, detail="esse job não guarda dados suficientes pra tentar de novo")
    worker.delete(job_id)
    return _job_dict(new_job)


@app.post("/api/jobs/{job_id}/open-manual")
def open_manual_job(job_id: str) -> dict:
    job = worker.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job não encontrado")
    try:
        downloads_service.open_manual_download(job)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/jobs/{job_id}/import-manual")
def import_manual_job(job_id: str) -> dict:
    job = worker.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job não encontrado")
    try:
        downloads_service.import_latest_manual_download(job)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    updated = worker.get(job_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="job não encontrado")
    return _job_dict(updated)


# --- library (unificada: manga + livros num só lugar) ---------------------

@app.get("/api/library")
def library(q: str = "", kind: str | None = None, page: int = 1, pageSize: int = 20) -> dict:
    kind = kind or None  # an empty "kind=" query param means "all", same as omitting it
    items: list[dict] = []
    if kind in (None, "manga"):
        manga_items, _ = repository.list_library(page=1, page_size=100_000)
        items.extend(_manga_dict(m) for m in manga_items)
    if kind in (None, "book"):
        book_items, _ = repository.list_downloaded_books(page=1, page_size=100_000)
        items.extend(_book_dict(b) for b in book_items)

    needle = q.strip().lower()
    if needle:
        items = [it for it in items if needle in (it["title"] or "").lower()]

    items.sort(key=lambda it: it.get("lastUpdated") or "", reverse=True)

    total = len(items)
    total_pages = max((total + pageSize - 1) // pageSize, 1)
    page = max(page, 1)
    start = (page - 1) * pageSize
    page_items = items[start : start + pageSize]

    return {"items": page_items, "total": total, "totalPages": total_pages}


@app.delete("/api/library/item")
def delete_library_item(kind: str = Query(...), item_id: str = Query(..., alias="id")) -> dict:
    normalized = kind.strip().lower()
    if normalized == "manga":
        manga = repository.get_manga_by_id(item_id)
        if manga is None:
            raise HTTPException(status_code=404, detail="mangá não encontrado na biblioteca")
        removed = _remove_download_path(manga.local_path)
        repository.delete_manga(item_id)
        repository.delete_reading_state(item_id)
        return {"ok": True, "removedFiles": removed, "stats": config.compute_storage_stats()}

    if normalized in {"book", "books"}:
        book = repository.get_book_by_id(item_id)
        if book is None:
            raise HTTPException(status_code=404, detail="livro/quadrinho não encontrado na biblioteca")
        removed = _remove_download_path(book.local_path)
        repository.delete_book(item_id)
        repository.delete_reading_state(item_id)
        return {"ok": True, "removedFiles": removed, "stats": config.compute_storage_stats()}

    raise HTTPException(status_code=400, detail="kind deve ser manga ou book")


@app.delete("/api/library/all")
def clear_downloaded_library() -> dict:
    active_jobs = [job for job in worker.snapshot() if job.status in {"pending", "running"}]
    if active_jobs:
        raise HTTPException(status_code=409, detail="Espere os downloads em andamento terminarem antes de limpar tudo")
    manga_items, _ = repository.list_library(page=1, page_size=100_000)
    book_items, _ = repository.list_downloaded_books(page=1, page_size=100_000)
    removed = 0
    seen_paths: set[str] = set()
    for item in [*manga_items, *book_items]:
        local_path = item.local_path or ""
        if local_path and local_path not in seen_paths:
            seen_paths.add(local_path)
            removed += 1 if _remove_download_path(local_path) else 0

    removed += _clear_directory_contents(config.get_library_path())
    removed += _clear_directory_contents(config.get_books_library_path())
    repository.delete_downloaded_manga()
    repository.delete_downloaded_books()
    repository.delete_all_reading_state()
    return {"ok": True, "removedFiles": removed, "stats": config.compute_storage_stats()}


# --- reader (mangá: capítulos + páginas de dentro do CBZ; livro: arquivo cru) ---

@app.get("/api/library/manga/chapters")
def manga_chapters(id: str = Query(...)) -> dict:
    return {"chapters": reader_service.list_chapters(id)}


@app.get("/api/library/manga/pages")
def manga_pages(id: str = Query(...), chapter: str = Query(...)) -> dict:
    return {"pages": reader_service.list_pages(id, chapter)}


@app.get("/api/library/manga/page")
def manga_page(id: str = Query(...), chapter: str = Query(...), page: str = Query(...)) -> Response:
    data = reader_service.read_page(id, chapter, page)
    if data is None:
        raise HTTPException(status_code=404, detail="página não encontrada")
    media_type = mimetypes.guess_type(page)[0] or "application/octet-stream"
    return Response(content=data, media_type=media_type)


@app.get("/api/library/books/file")
def book_file(id: str = Query(...)) -> Response:
    path = reader_service.book_file_path(id)
    if path is None:
        raise HTTPException(status_code=404, detail="arquivo não encontrado")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return Response(content=path.read_bytes(), media_type=media_type)


@app.get("/api/library/books/text")
def book_text(id: str = Query(...)) -> dict:
    try:
        return reader_service.book_text_content(id)
    except Exception as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc


@app.get("/api/library/books/archive/pages")
def book_archive_pages(id: str = Query(...)) -> dict:
    try:
        return {"pages": reader_service.list_book_archive_pages(id)}
    except Exception as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc


@app.get("/api/library/books/archive/page")
def book_archive_page(id: str = Query(...), page: str = Query(...)) -> Response:
    data = reader_service.read_book_archive_page(id, page)
    if data is None:
        raise HTTPException(status_code=404, detail="página não encontrada")
    media_type = mimetypes.guess_type(page)[0] or "application/octet-stream"
    return Response(content=data, media_type=media_type)


# --- reading position (retoma de onde parou) --------------------------------

@app.get("/api/reading-state")
def get_reading_state(id: str = Query(...)) -> dict:
    return {"state": repository.get_reading_state(id)}


@app.post("/api/reading-state")
def save_reading_state(payload: dict = Body(...)) -> dict:
    item_id = payload.get("id")
    kind = payload.get("kind")
    if not item_id or not kind:
        raise HTTPException(status_code=400, detail="id e kind são obrigatórios")
    repository.save_reading_state(
        item_id,
        kind,
        chapter_file=payload.get("chapterFile"),
        page_index=payload.get("pageIndex"),
        location=payload.get("location"),
    )
    return {"ok": True}


# --- settings --------------------------------------------------------------

@app.get("/api/settings")
def get_settings() -> dict:
    stats = config.compute_storage_stats()
    return {
        "libraryPath": str(config.get_library_path()),
        "booksLibraryPath": str(config.get_books_library_path()),
        "stats": stats,
    }


@app.post("/api/settings/library-path")
def set_library_path(payload: dict = Body(...)) -> dict:
    path = (payload or {}).get("path", "").strip()
    if not path:
        raise HTTPException(status_code=400, detail="Informe um caminho de pasta")
    try:
        config.set_library_path(Path(path))
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Não deu pra usar essa pasta: {exc}") from exc
    return get_settings()


if _WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
