"""Small helpers for sources that expose direct ebook file URLs."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from sapphirebox.core.downloader import safe_filename
from sapphirebox.core.models import Book, BookFileOption

_SIZE_RE = re.compile(r"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>kb|mb|gb|b)\b", re.IGNORECASE)
_CONTENT_RANGE_RE = re.compile(r"/(\d+)\s*$")
_CONTENT_DISPOSITION_FILENAME_RE = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', re.IGNORECASE)
_MIME_EXT = {
    "application/pdf": "pdf",
    "application/epub+zip": "epub",
    "application/x-mobipocket-ebook": "mobi",
    "text/plain": "txt",
}
# A download link is sometimes itself a script endpoint (LibGen's final
# redirect target is literally .../get.php?...) — the real filename lives
# in Content-Disposition instead, so a bare URL-path suffix that looks
# like a script extension is worse than no suffix at all.
_SCRIPT_EXTS = {"php", "php3", "php4", "php5", "asp", "aspx", "jsp", "cgi", "do", "action"}


def clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def parse_size_label(label: str | None) -> int | None:
    match = _SIZE_RE.search(label or "")
    if match is None:
        return None
    value = float(match.group("num").replace(",", "."))
    unit = match.group("unit").lower()
    multiplier = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}[unit]
    return int(value * multiplier)


def format_size(bytes_count: int | None) -> str | None:
    if bytes_count is None:
        return None
    units = ("B", "KB", "MB", "GB")
    value = float(bytes_count)
    unit = 0
    while value >= 1024 and unit < len(units) - 1:
        value /= 1024
        unit += 1
    return f"{value:.0f} {units[unit]}" if unit == 0 else f"{value:.1f} {units[unit]}"


def selected_option(options: list[BookFileOption], requested_format: str | None) -> BookFileOption | None:
    if not options:
        return None
    requested = (requested_format or "").lower().strip(".")
    for option in options:
        if option.format.lower() == requested:
            return option
    return min(options, key=lambda o: o.size_bytes if o.size_bytes is not None else 10**18)


def probe_file_size(client: httpx.Client, url: str, referer: str | None = None) -> int | None:
    headers = {"Referer": referer} if referer else None
    try:
        head = client.head(url, headers=headers)
        content_type = head.headers.get("content-type", "").lower()
        content_length = head.headers.get("content-length")
        if head.status_code < 400 and content_length and "text/html" not in content_type:
            return int(content_length)
    except Exception:
        pass

    try:
        req_headers = {"Range": "bytes=0-0"}
        if referer:
            req_headers["Referer"] = referer
        with client.stream("GET", url, headers=req_headers) as resp:
            content_range = resp.headers.get("content-range", "")
            match = _CONTENT_RANGE_RE.search(content_range)
            if match:
                return int(match.group(1))
            content_type = resp.headers.get("content-type", "").lower()
            content_length = resp.headers.get("content-length")
            if resp.status_code < 400 and content_length and "text/html" not in content_type:
                return int(content_length)
    except Exception:
        return None
    return None


def _ext_from_content_disposition(header_value: str | None) -> str | None:
    match = _CONTENT_DISPOSITION_FILENAME_RE.search(header_value or "")
    if not match:
        return None
    suffix = Path(unquote(match.group(1))).suffix.lower().lstrip(".")
    return suffix or None


def infer_ext(url: str, content_type: str, fallback: str, content_disposition: str | None = None) -> str:
    from_disposition = _ext_from_content_disposition(content_disposition)
    if from_disposition:
        return from_disposition
    suffix = Path(unquote(urlparse(url).path)).suffix.lower().lstrip(".")
    if suffix and suffix not in _SCRIPT_EXTS:
        return suffix
    mime = content_type.split(";", 1)[0].strip().lower()
    return _MIME_EXT.get(mime, fallback.lower().strip(".") or "bin")


def download_direct_file(
    client: httpx.Client,
    book: Book,
    option: BookFileOption,
    dest_dir: Path,
    on_progress=None,
    referer: str | None = None,
) -> Book:
    dest_dir.mkdir(parents=True, exist_ok=True)
    headers = {"Referer": referer} if referer else None
    if on_progress:
        on_progress(3, f"Baixando {option.format.upper()}...")

    size = 0
    path: Path | None = None
    with client.stream("GET", option.url, headers=headers) as resp:
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "").lower()
        if "text/html" in content_type:
            raise RuntimeError("A fonte devolveu uma página HTML no lugar do arquivo.")
        ext = infer_ext(option.url, content_type, option.format, resp.headers.get("content-disposition"))
        path = dest_dir / f"{safe_filename(book.title)}.{ext}"
        total = option.size_bytes
        if total is None and resp.headers.get("content-length"):
            total = int(resp.headers["content-length"])
        with open(path, "wb") as file:
            for chunk in resp.iter_bytes():
                if not chunk:
                    continue
                file.write(chunk)
                size += len(chunk)
                if on_progress and total:
                    pct = min(98, 5 + int((size / total) * 93))
                    on_progress(pct, f"Baixando {option.format.upper()}... {format_size(size) or ''}")

    book.format = (path.suffix.lstrip(".") if path else option.format).lower()
    book.local_path = str(path)
    book.file_size_bytes = size
    book.file_options = [option]
    if on_progress:
        on_progress(99, "Arquivo salvo.")
    return book
