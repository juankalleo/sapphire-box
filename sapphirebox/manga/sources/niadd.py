"""Niadd source: search, details, and a self-contained chapter
downloader (fetches pages, saves images, packages them into a CBZ)."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from sapphirebox.core.downloader import (
    extract_image_url,
    find_cover_in_tree,
    guess_image_ext,
    new_client,
    normalize_image_url,
    title_from_folder,
)
from sapphirebox.core.models import Manga, MangaChapterOption
from sapphirebox.manga.sources.base import (
    MangaSource,
    ProgressCallback,
    chapter_label,
    parse_requested_chapters,
)

BASE = "https://br.niadd.com"

_COVER_CARD_RE = re.compile(
    r"""<a[^>]*href=["'](?P<href>(?:https?://br\.niadd\.com)?/manga/[^"']+)["'][^>]*>\s*"""
    r"""<div[^>]*class=["'][^"']*manga-img[^"']*["'][^>]*>\s*<img[^>]+(?:data-src|src)=["'](?P<cover>[^"']+)["']""",
    re.IGNORECASE | re.DOTALL,
)

_CHAPTER_SELECTOR_CHAIN = ["a.chapter-item", "ul.chapters a", "a[href*='chapter']", "a[href*='capitulo']", "a[href*='/c/']"]
_IMAGE_SELECTOR_CHAIN = ["img.page-img", "img#image", "div.reading-content img", "img"]
_SKIP_MARKERS = ("brand", "logo", "avatar", "favicon")


def _to_abs(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(BASE + "/", href)


def normalize_niadd_url(url: str) -> str:
    """Turn a chapter link into the manga root, so manual pastes still work."""
    low = url.lower()
    idx = low.find("/manga/")
    if idx == -1:
        return url

    prefix = url[: idx + len("/manga/")]
    suffix = url[idx + len("/manga/") :]
    suffix_no_q = suffix.split("?")[0].split("#")[0]
    low_suffix = suffix_no_q.lower()

    html_idx = low_suffix.find(".html")
    if html_idx != -1:
        return prefix + suffix_no_q[: html_idx + 5]

    for marker in ("/chapter", "/capitulo", "/ch-", "/ch_"):
        m_idx = low_suffix.find(marker)
        if m_idx != -1:
            return prefix + suffix_no_q[:m_idx].rstrip("/")

    seg_end = suffix_no_q.find("/")
    if seg_end != -1:
        return prefix + suffix_no_q[:seg_end]
    return url


def _cover_by_href_map(soup: BeautifulSoup, html: str) -> dict[str, str]:
    covers: dict[str, str] = {}
    for m in _COVER_CARD_RE.finditer(html):
        abs_href = _to_abs(m.group("href"))
        covers.setdefault(abs_href, normalize_image_url(m.group("cover")))

    for card in soup.select("li, article, .book-item, .manga-item, .list-item, .media"):
        anchor = next(
            (a for a in card.select("a[href]") if "/manga/" in a.get("href", "") and "/capitulo-" not in a.get("href", "")),
            None,
        )
        if anchor is None:
            continue
        abs_href = _to_abs(anchor["href"])
        cover = extract_image_url(card)
        if cover:
            covers.setdefault(abs_href, normalize_image_url(cover))
    return covers


def _parse_cards(html: str, query: str) -> list[Manga]:
    soup = BeautifulSoup(html, "html.parser")
    cover_by_href = _cover_by_href_map(soup, html)
    q = query.strip().lower()
    seen: set[str] = set()
    out: list[Manga] = []

    for a in soup.select("a[href*='/manga/']"):
        href = a.get("href")
        if not href or "/manga/.html" in href:
            continue
        abs_href = _to_abs(href)
        if abs_href in seen:
            continue
        title = a.get_text(" ", strip=True) or (a.get("title") or "").strip()
        if not title or (q and q not in title.lower()):
            continue
        seen.add(abs_href)
        out.append(
            Manga(
                id=abs_href,
                title=title,
                source_id="niadd",
                source_name="Niadd",
                cover_path=cover_by_href.get(abs_href),
                status="ongoing",
            )
        )
    return out


def search(query: str) -> list[Manga]:
    q = query.strip()
    if not q:
        candidates = [f"{BASE}/list/Hot-Manga/", f"{BASE}/list/New-Update/", f"{BASE}/"]
    else:
        encoded = quote(q)
        candidates = [f"{BASE}/search/?search_type=1&name={encoded}", f"{BASE}/search/?name={encoded}"]

    seen_ids: set[str] = set()
    merged: list[Manga] = []
    last_error: str | None = None
    with new_client(timeout=12) as client:
        for url in candidates:
            try:
                resp = client.get(url)
            except httpx.HTTPError as exc:
                last_error = f"request error for {url}: {exc}"
                continue
            if resp.status_code != 200:
                last_error = f"http status {resp.status_code} for {url}"
                continue
            for manga in _parse_cards(resp.text, q):
                if manga.id not in seen_ids:
                    seen_ids.add(manga.id)
                    merged.append(manga)

    if not merged and last_error:
        raise RuntimeError(f"Niadd scraping failed: {last_error}")

    return merged[:80]


def get_details(manga_id: str) -> Manga | None:
    for manga in search(""):
        if manga.id == manga_id:
            return manga
    return None


def _first_matching(soup: BeautifulSoup, selectors: list[str]) -> list:
    for sel in selectors:
        found = soup.select(sel)
        if found:
            return found
    return []


def _chapter_links_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    chapter_anchors = _first_matching(soup, _CHAPTER_SELECTOR_CHAIN)
    chapter_links = [a["href"] for a in chapter_anchors if a.get("href")]
    if not chapter_links:
        chapter_links = [
            a["href"]
            for a in soup.select("a[href]")
            if a.get("href") and ("chapter" in a["href"] or "cap" in a["href"])
        ]
    out: list[str] = []
    seen: set[str] = set()
    for link in chapter_links:
        abs_link = _to_abs(link)
        if abs_link not in seen:
            seen.add(abs_link)
            out.append(abs_link)
    return out


def list_chapters(manga_url: str) -> list[MangaChapterOption]:
    manga_url = normalize_niadd_url(manga_url)
    with new_client(timeout=20) as client:
        html = client.get(manga_url).text
    return [
        MangaChapterOption(index=idx, label=chapter_label(url, idx)[0], url=url)
        for idx, url in enumerate(_chapter_links_from_html(html), start=1)
    ]


def download_chapters(
    manga_url: str,
    dest: Path,
    chapters: str = "all",
    fmt: str = "cbz",
    on_progress: ProgressCallback | None = None,
) -> Manga:
    manga_url = normalize_niadd_url(manga_url)
    dest.mkdir(parents=True, exist_ok=True)
    fmt = fmt.strip().lower()

    with new_client(timeout=20) as client:
        html = client.get(manga_url).text

        abs_links = _chapter_links_from_html(html)
        if not abs_links:
            raise RuntimeError("No chapter links found on Niadd page")

        selected = parse_requested_chapters(chapters, len(abs_links))
        if not selected:
            raise RuntimeError("No chapters selected from requested range")

        total = len(selected)
        total_saved_pages = 0
        total_chapters_with_pages = 0

        for sel_idx, chapter_idx in enumerate(selected):
            chapter_url = abs_links[chapter_idx - 1] if chapter_idx - 1 < len(abs_links) else abs_links[0]
            chapter_display, chapter_file_label = chapter_label(chapter_url, chapter_idx)

            ch_html = client.get(chapter_url).text
            ch_soup = BeautifulSoup(ch_html, "html.parser")
            images: list[str] = []
            for sel in _IMAGE_SELECTOR_CHAIN:
                found = ch_soup.select(sel)
                if found:
                    images = [el.get("data-src") or el.get("src") for el in found]
                    images = [src for src in images if src]
                    if images:
                        break

            if not images:
                continue

            filtered = [
                src
                for src in images
                if any(ext in src.lower() for ext in (".jpg", ".jpeg", ".png", ".webp"))
                and not any(marker in src.lower() for marker in _SKIP_MARKERS)
            ]
            page_urls = filtered or images

            chapter_dir = dest / f"chapter_{chapter_file_label}"
            chapter_dir.mkdir(parents=True, exist_ok=True)
            chapter_saved = 0
            for i, img_url in enumerate(page_urls):
                abs_img = _to_abs(img_url)
                try:
                    resp = client.get(abs_img)
                    resp.raise_for_status()
                except httpx.HTTPError:
                    continue
                ext = guess_image_ext(abs_img)
                (chapter_dir / f"{i + 1:03d}.{ext}").write_bytes(resp.content)
                chapter_saved += 1
                total_saved_pages += 1

                if on_progress:
                    chapter_pct = int((i + 1) * 100 / len(page_urls))
                    global_pct = int(sel_idx * 100 / total) + int(chapter_pct / total)
                    on_progress(min(global_pct, 99), f"Capítulo {chapter_display} página {i + 1}")

            if chapter_saved == 0:
                continue
            total_chapters_with_pages += 1

            if fmt == "cbz":
                cbz_path = dest / f"chapter_{chapter_file_label}.cbz"
                with zipfile.ZipFile(cbz_path, "w", compression=zipfile.ZIP_STORED) as zf:
                    for page in sorted(chapter_dir.iterdir()):
                        if page.is_file():
                            zf.write(page, arcname=page.name)

    if total_saved_pages == 0:
        raise RuntimeError(f"No pages were downloaded from Niadd ({len(selected)} selected chapters)")

    if on_progress:
        on_progress(100, "completed")

    return Manga(
        id=manga_url,
        title=title_from_folder(dest),
        source_id="niadd",
        source_name="Niadd",
        cover_path=find_cover_in_tree(dest),
        status="unknown",
        local_path=str(dest),
        total_chapters=total_chapters_with_pages,
        downloaded_chapters=total_chapters_with_pages,
    )


class NiaddSource(MangaSource):
    id = "niadd"
    name = "Niadd"

    def search(self, query: str, page: int = 1) -> tuple[list[Manga], int]:
        return search(query), 1

    def get_details(self, manga_id: str) -> Manga | None:
        return get_details(manga_id)

    def list_chapters(self, manga_id: str) -> list[MangaChapterOption]:
        return list_chapters(manga_id)

    def download_chapters(
        self,
        manga_id: str,
        dest: Path,
        chapters: str,
        fmt: str,
        on_progress: ProgressCallback | None = None,
    ) -> Manga:
        return download_chapters(manga_id, dest, chapters, fmt, on_progress)
