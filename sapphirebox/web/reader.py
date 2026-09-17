"""Serves chapter/page listings and raw page bytes out of the CBZ files a
manga download already produces — and the raw file for a downloaded book
— so the web UI can read what it just downloaded without leaving the app.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup

from sapphirebox.library import repository

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


def _chapter_sort_key(stem: str) -> float:
    label = stem.removeprefix("chapter_").replace("_", ".")
    try:
        return float(label)
    except ValueError:
        return 0.0


def _safe_child_path(root: str, name: str) -> Path | None:
    """`name` comes from a query string — reject anything that isn't a
    plain filename directly inside `root` (no path traversal)."""
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    root_path = Path(root).resolve()
    candidate = (root_path / name).resolve()
    if candidate.parent != root_path:
        return None
    return candidate


def _page_sort_key(name: str) -> list[int | str]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def list_chapters(manga_id: str) -> list[dict]:
    manga = repository.get_manga_by_id(manga_id)
    if manga is None or not manga.local_path:
        return []
    root = Path(manga.local_path)
    if not root.is_dir():
        return []

    chapters = sorted(root.glob("chapter_*.cbz"), key=lambda p: _chapter_sort_key(p.stem))
    return [{"label": p.stem.removeprefix("chapter_").replace("_", "."), "file": p.name} for p in chapters]


def list_pages(manga_id: str, chapter_file: str) -> list[str]:
    manga = repository.get_manga_by_id(manga_id)
    if manga is None or not manga.local_path:
        return []
    cbz_path = _safe_child_path(manga.local_path, chapter_file)
    if cbz_path is None or not cbz_path.exists():
        return []
    with zipfile.ZipFile(cbz_path) as zf:
        return sorted(n for n in zf.namelist() if not n.endswith("/"))


def read_page(manga_id: str, chapter_file: str, page_name: str) -> bytes | None:
    manga = repository.get_manga_by_id(manga_id)
    if manga is None or not manga.local_path:
        return None
    cbz_path = _safe_child_path(manga.local_path, chapter_file)
    if cbz_path is None or not cbz_path.exists():
        return None
    with zipfile.ZipFile(cbz_path) as zf:
        if page_name not in zf.namelist():
            return None
        return zf.read(page_name)


def book_file_path(book_id: str) -> Path | None:
    """Books aren't looked up by id via a dedicated query yet — the
    library is small enough that scanning the full list is simpler than
    adding a new repository method for one lookup."""
    items, _ = repository.list_downloaded_books(page=1, page_size=100_000)
    for b in items:
        if b.id == book_id and b.local_path:
            path = Path(b.local_path)
            return path if path.exists() else None
    return None


def book_text_content(book_id: str) -> dict:
    path = book_file_path(book_id)
    if path is None:
        raise RuntimeError("arquivo não encontrado")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        tool = shutil.which("pdftotext")
        if tool is None:
            raise RuntimeError("pdftotext não está instalado para extrair texto desse PDF")
        proc = subprocess.run(
            [tool, "-layout", str(path), "-"],
            capture_output=True,
            timeout=45,
            check=False,
        )
        if proc.returncode != 0:
            err = _decode_text(proc.stderr).strip()
            raise RuntimeError(err or "não deu para extrair texto desse PDF")
        text = _decode_text(proc.stdout).strip()
        if not text:
            raise RuntimeError("esse PDF não tem texto extraível; provavelmente é imagem/scanner")
        return {"format": "pdf", "text": text}

    data = path.read_bytes()
    if suffix in {".html", ".htm", ".xhtml"}:
        soup = BeautifulSoup(_decode_text(data), "html.parser")
        return {"format": suffix.lstrip("."), "text": soup.get_text("\n", strip=True)}
    if suffix in {".txt", ".md", ".markdown", ".csv", ".log"}:
        return {"format": suffix.lstrip("."), "text": _decode_text(data)}

    raise RuntimeError(f"o leitor interno ainda não extrai texto de {suffix or 'arquivo sem extensão'}")


def _book_archive_path(book_id: str) -> Path | None:
    path = book_file_path(book_id)
    if path is None or path.suffix.lower() not in {".cbz", ".cbr"}:
        return None
    return path


def _zip_image_pages(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        pages = [name for name in zf.namelist() if Path(name).suffix.lower() in _IMAGE_EXTS and not name.endswith("/")]
    return sorted(pages, key=_page_sort_key)


def _bsdtar_image_pages(path: Path) -> list[str]:
    tool = shutil.which("bsdtar")
    if tool is None:
        raise RuntimeError("bsdtar não está instalado para abrir CBR")
    proc = subprocess.run([tool, "-tf", str(path)], capture_output=True, timeout=30, check=False)
    if proc.returncode != 0:
        err = _decode_text(proc.stderr).strip()
        raise RuntimeError(err or "não deu para listar páginas do CBR")
    pages = [
        line.strip()
        for line in _decode_text(proc.stdout).splitlines()
        if Path(line.strip()).suffix.lower() in _IMAGE_EXTS
    ]
    return sorted(pages, key=_page_sort_key)


def list_book_archive_pages(book_id: str) -> list[str]:
    path = _book_archive_path(book_id)
    if path is None:
        return []
    if path.suffix.lower() == ".cbz":
        return _zip_image_pages(path)
    return _bsdtar_image_pages(path)


def read_book_archive_page(book_id: str, page_name: str) -> bytes | None:
    path = _book_archive_path(book_id)
    if path is None:
        return None
    pages = list_book_archive_pages(book_id)
    if page_name not in pages:
        return None
    if path.suffix.lower() == ".cbz":
        with zipfile.ZipFile(path) as zf:
            return zf.read(page_name)

    tool = shutil.which("bsdtar")
    if tool is None:
        return None
    proc = subprocess.run([tool, "-xOf", str(path), page_name], capture_output=True, timeout=30, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout
