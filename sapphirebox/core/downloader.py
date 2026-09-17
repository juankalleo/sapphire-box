"""Shared HTTP client and small file helpers used by every scraper: a
browser-like user agent, anti-bot page detection, and image-extension
sniffing."""
from __future__ import annotations

import re
import ssl
from pathlib import Path

import certifi
import httpx
from bs4.element import Tag

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_BLOCK_MARKERS = (
    "sorry, you have been blocked",
    "attention required",
    "cloudflare",
    "cf-challenge",
    "/cdn-cgi/",
)

_IMAGE_MAGIC = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)

# Chaquopy (Python embedded in the Android app) ships its own OpenSSL and
# only trusts certifi's bundled CA file out of the box. That bundle is
# frozen at whatever version was resolved when the APK was last built, so
# it can miss a root/intermediate a site rotates onto later and every
# HTTPS request then dies with CERTIFICATE_VERIFY_FAILED — which is
# invisible from a desktop dev machine using its OS's own up-to-date
# trust store. Android itself keeps a full, current CA trust store as
# plain PEM files, world-readable with no permission needed, at the paths
# below — load those on top of certifi so the embedded interpreter trusts
# the same roots the rest of the phone (browser, other apps) already
# does. This is a no-op on desktop/CI since neither path exists there.
_ANDROID_SYSTEM_CA_DIRS = (
    "/apex/com.android.conscrypt/cacerts",
    "/system/etc/security/cacerts",
)

_ssl_context: ssl.SSLContext | None = None


def _build_ssl_context() -> ssl.SSLContext:
    global _ssl_context
    if _ssl_context is not None:
        return _ssl_context

    ctx = ssl.create_default_context(cafile=certifi.where())
    for cert_dir in _ANDROID_SYSTEM_CA_DIRS:
        dir_path = Path(cert_dir)
        if not dir_path.is_dir():
            continue
        for cert_file in dir_path.iterdir():
            try:
                pem = cert_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "BEGIN CERTIFICATE" not in pem:
                continue
            try:
                ctx.load_verify_locations(cadata=pem)
            except ssl.SSLError:
                continue

    _ssl_context = ctx
    return ctx


def new_client(timeout: float = 20.0) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"},
        timeout=timeout,
        follow_redirects=True,
        verify=_build_ssl_context(),
    )


def looks_blocked(html: str) -> bool:
    low = html.lower()
    return any(marker in low for marker in _BLOCK_MARKERS)


def guess_image_ext(url_or_bytes: str | bytes) -> str:
    if isinstance(url_or_bytes, bytes):
        if url_or_bytes[:12].startswith(b"RIFF") and b"WEBP" in url_or_bytes[:16]:
            return "webp"
        for magic, ext in _IMAGE_MAGIC:
            if url_or_bytes.startswith(magic):
                return ext
        return "jpg"

    low = url_or_bytes.lower()
    if ".webp" in low:
        return "webp"
    if ".png" in low:
        return "png"
    if ".gif" in low:
        return "gif"
    return "jpg"


def safe_filename(name: str, fallback: str = "item", max_len: int = 150) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", name).strip().strip(".")
    return (cleaned or fallback)[:max_len]


def slug_from_url(url: str, fallback: str) -> str:
    trimmed = url.rstrip("/")
    seg = trimmed.rsplit("/", 1)[-1] or fallback
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", seg).strip("_")
    return slug or fallback


def save_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


_COVER_NAMES = ("cover.jpg", "cover.png", "cover.webp")


def title_from_folder(path: Path) -> str:
    return path.name.replace("_", " ")


def count_downloaded_chapters(root: Path) -> int:
    """Counts .cbz files directly under `root` or one level down."""
    if not root.exists():
        return 0
    count = 0
    for entry in root.iterdir():
        if entry.is_file() and entry.suffix.lower() == ".cbz":
            count += 1
        elif entry.is_dir():
            count += sum(1 for f in entry.iterdir() if f.is_file() and f.suffix.lower() == ".cbz")
    return count


def find_cover_in_tree(root: Path) -> str | None:
    """Known cover filenames at the root, else the first page image found
    one level down (mirrors find_cover_in_downloaded_tree in download.rs)."""
    for name in _COVER_NAMES:
        candidate = root / name
        if candidate.is_file():
            return str(candidate)
    if not root.exists():
        return None
    for child in sorted(root.iterdir()):
        if child.is_dir():
            for grandchild in sorted(child.iterdir()):
                if grandchild.is_file() and grandchild.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                    return str(grandchild)
    return None


_IMG_ATTRS = (
    "data-src",
    "data-lazy-src",
    "data-original",
    "data-srcset",
    "data-lazy-srcset",
    "srcset",
    "src",
    "style",
)
_URL_RE = re.compile(r"url\((.*?)\)", re.IGNORECASE)


def normalize_image_url(raw: str) -> str:
    trimmed = raw.strip()
    if trimmed.startswith("//"):
        return f"https:{trimmed}"
    return trimmed


def _from_attr_value(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    if "url(" in value:
        m = _URL_RE.search(value)
        if m:
            return normalize_image_url(m.group(1).strip("'\""))
        return None
    # srcset-style: "url1 1x, url2 2x" -> take the first URL
    first = value.split(",")[0].split()[0].strip()
    return normalize_image_url(first) if first else None


_SPLIT_CHARS = re.compile(r"""['"\s<>(),]+""")
_TRIM_CHARS = "][;"


def extract_image_urls_from_text(raw: str) -> list[str]:
    """Manga sites often embed page image URLs in inline <script> blobs."""
    normalized = raw.replace("\\/", "/")
    urls = set()
    for token in _SPLIT_CHARS.split(normalized):
        token = token.strip(_TRIM_CHARS)
        low = token.lower()
        if any(ext in low for ext in (".jpg", ".jpeg", ".png", ".webp")) and (
            low.startswith("http://") or low.startswith("https://") or low.startswith("//") or low.startswith("/")
        ):
            urls.add(token)
    return sorted(urls)


def extract_chapter_urls_from_text(raw: str) -> list[str]:
    normalized = raw.replace("\\/", "/")
    urls = set()
    for token in _SPLIT_CHARS.split(normalized):
        token = token.strip(_TRIM_CHARS)
        low = token.lower()
        if "/capitulo-" in low and (
            low.startswith("http://") or low.startswith("https://") or low.startswith("//") or low.startswith("/")
        ):
            urls.add(token)
    return sorted(urls)


def extract_image_url(el: Tag) -> str | None:
    """Best-effort cover/page image lookup inside a card element.

    Ports WebScraper::extract_image_url_from_element: check the common
    lazy-load attributes in priority order, on any img/source/styled
    descendant, then fall back to the element's own inline style.
    """
    for node in el.select("img, source, [style]"):
        for attr in _IMG_ATTRS:
            value = node.get(attr)
            if value:
                found = _from_attr_value(value)
                if found:
                    return found

    style = el.get("style")
    if style:
        return _from_attr_value(style)
    return None
