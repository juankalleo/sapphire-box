"""MangaLivre source — port of scraper/mod.rs's MangaLivre functions.

MangaLivre has real server-side pagination and a fairly stable card
layout, so it gets its own paginated search instead of going through the
generic light/full search split used for the other custom sources.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from sapphirebox.core.downloader import (
    extract_chapter_urls_from_text,
    extract_image_url,
    extract_image_urls_from_text,
    find_cover_in_tree,
    guess_image_ext,
    looks_blocked,
    new_client,
    normalize_image_url,
    title_from_folder,
)
from sapphirebox.core.models import Manga, MangaChapterOption
from sapphirebox.manga.sources.base import (
    MangaSource,
    ProgressCallback,
    chapter_label,
    chapter_number_from_url,
    parse_requested_chapters,
)

_SKIP_MARKERS = ("logo", "avatar", "favicon")

BASE = "https://mangalivre.to"
MIRROR = "https://mangalivre.tv"
_PAGE_RE = re.compile(r"/page/(\d+)/")


def _to_abs(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(BASE + "/", href)


def _manga_root_url(manga_id: str) -> str:
    url = manga_id if manga_id.startswith("http") else f"{BASE}/manga/{manga_id.strip('/')}/"
    return url.split("/capitulo-")[0] + "/" if "/capitulo-" in url else url


def _manga_url_candidates(manga_id: str) -> list[str]:
    url = _manga_root_url(manga_id)
    preferred = url.replace("://mangalivre.tv", "://mangalivre.to")
    alternate = preferred.replace("://mangalivre.to", "://mangalivre.tv")
    out: list[str] = []
    for candidate in (preferred, url, alternate):
        if candidate not in out:
            out.append(candidate)
    return out


def _parse_total_pages(html: str) -> int:
    pages = [int(m) for m in _PAGE_RE.findall(html)]
    return max(pages) if pages else 1


def _mk_manga(url: str, title: str, cover: str | None, synopsis: str | None = None, total_chapters: int = 0) -> Manga:
    return Manga(
        id=url,
        title=title,
        source_id="mangalivre",
        source_name="Manga Livre",
        cover_path=cover,
        synopsis=synopsis,
        status="ongoing",
        total_chapters=total_chapters,
    )


def _cover_by_href_map(soup: BeautifulSoup) -> dict[str, str]:
    covers: dict[str, str] = {}
    for card in soup.select("li, article, .page-item-detail, .c-tabs-item, .row.c-tabs-item"):
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

    # Raw-HTML regex fallback for layouts where title/link and image aren't
    # in the same parsed subtree (mirrors the Rust regex fallback).
    for m in re.finditer(
        r"""<a[^>]*href=["'](?P<href>[^"']*/manga/[^"']*)["'][^>]*>.*?<img[^>]+(?:data-src|src)=["'](?P<cover>[^"']+)["']""",
        str(soup),
        re.IGNORECASE | re.DOTALL,
    ):
        abs_href = _to_abs(m.group("href"))
        covers.setdefault(abs_href, normalize_image_url(m.group("cover")))

    return covers


def _parse_cards(html: str, query: str) -> list[Manga]:
    soup = BeautifulSoup(html, "html.parser")
    q = query.strip().lower()
    cover_by_href = _cover_by_href_map(soup)
    seen: set[str] = set()
    out: list[Manga] = []

    # 1) Native MangaLivre list layout.
    for li in soup.select("ul.seriesList > li"):
        anchor = next((a for a in li.select("a[href]") if "/manga/" in a.get("href", "")), None)
        if anchor is None or "/capitulo-" in anchor["href"]:
            continue
        abs_href = _to_abs(anchor["href"])
        if abs_href in seen:
            continue

        title_el = li.select_one("span.series-title, h2, h3")
        title = title_el.get_text(" ", strip=True) if title_el else (anchor.get("title") or "").strip()
        if not title or (q and q not in title.lower()):
            continue

        cover = extract_image_url(li) or cover_by_href.get(abs_href)
        desc_el = li.select_one(".series-desc")
        synopsis = " ".join(desc_el.get_text(" ", strip=True).split()) if desc_el else None
        chapters_el = li.select_one("span.series-chapters")
        total_chapters = 0
        if chapters_el:
            digits = "".join(c for c in chapters_el.get_text() if c.isdigit())
            total_chapters = int(digits) if digits else 0

        seen.add(abs_href)
        out.append(_mk_manga(abs_href, title, cover, synopsis, total_chapters))

    if out:
        return out

    # 2) Madara-theme catalog cards (mangalivre.to/manga/ and its pages) —
    # each card also carries a chapter list AND an author link inside the
    # same container, both of which the old broad ".page-item-detail a"
    # selector below picked up as if they were separate manga ("TurtleMe",
    # "Masashi Kishimoto" showing up as titles). Scoping to the title's own
    # wrapper avoids that.
    for card in soup.select("div.page-item-detail"):
        anchor = card.select_one(".post-title a[href], .item-summary h3 a[href]")
        if anchor is None:
            continue
        href = anchor.get("href")
        if not href or "/capitulo-" in href:
            continue
        abs_href = _to_abs(href)
        if abs_href in seen:
            continue
        title = anchor.get_text(" ", strip=True)
        if not title or (q and q not in title.lower()):
            continue
        seen.add(abs_href)
        cover = extract_image_url(card) or cover_by_href.get(abs_href)
        out.append(_mk_manga(abs_href, title, cover))

    if out:
        return out

    # 3) Heading anchors.
    for a in soup.select(
        "h2 a[href*='/manga/'], h3 a[href*='/manga/'], .post-title a, .entry-title a"
    ):
        href = a.get("href")
        if not href or "/capitulo-" in href:
            continue
        abs_href = _to_abs(href)
        if abs_href in seen:
            continue
        title = a.get_text(" ", strip=True)
        if not title or (q and q not in title.lower()):
            continue
        seen.add(abs_href)
        out.append(_mk_manga(abs_href, title, cover_by_href.get(abs_href)))

    if out:
        return out

    # 4) Generic anchor fallback.
    for a in soup.select("a[href*='/manga/'], a[title][href]"):
        href = a.get("href")
        if not href or "/capitulo-" in href:
            continue
        abs_href = _to_abs(href)
        if abs_href in seen:
            continue
        title = a.get_text(" ", strip=True) or (a.get("title") or "").strip()
        if not title or (q and q not in title.lower()):
            continue
        seen.add(abs_href)
        out.append(_mk_manga(abs_href, title, cover_by_href.get(abs_href)))

    return out


def search_paginated(query: str, page: int = 1) -> tuple[list[Manga], int]:
    page = max(page, 1)
    q = query.strip()
    encoded = quote(q)

    if not q:
        # The homepage is a mix of sliders/menus/widgets with barely any
        # real catalog content — "Ver todos os mangás" (/manga/) is the
        # actual archive: real cards, and (unlike the homepage) genuine
        # further pages via /manga/page/N/.
        candidates = [f"{BASE}/manga/"] if page == 1 else [f"{BASE}/manga/page/{page}/"]
        candidates += [f"{MIRROR}/manga/"] if page == 1 else [f"{MIRROR}/manga/page/{page}/"]
    elif page == 1:
        candidates = [f"{BASE}/?s={encoded}&post_type=wp-manga", f"{MIRROR}/?s={encoded}&post_type=wp-manga"]
    else:
        # The theme links search results to /page/N/?s=... ("Older Posts"),
        # but that combination 404s on both mirrors — confirmed against
        # several queries, not query-specific. There's no working URL to
        # fetch a second page of search results, so don't pretend there is.
        return [], 1

    last_error: str | None = None
    with new_client(timeout=15) as client:
        for url in candidates:
            try:
                resp = client.get(url)
            except httpx.HTTPError as exc:
                last_error = f"request error for {url}: {exc}"
                continue
            if resp.status_code != 200:
                last_error = f"http status {resp.status_code} for {url}"
                continue
            html = resp.text
            if looks_blocked(html):
                last_error = f"blocked by anti-bot at {url}"
                continue

            # Search-results pagination is confirmed broken (see above) —
            # only trust the "there's a next page" signal in browse mode.
            total_pages = max(_parse_total_pages(html), page) if not q else 1
            items = _parse_cards(html, q)
            if items:
                return items, total_pages
            last_error = f"parsed 0 items for {url}"

    raise RuntimeError(f"MangaLivre scraping failed: {last_error or 'unknown error'}")


def get_details(manga_id: str) -> Manga | None:
    last_error = "unknown error"
    with new_client(timeout=20) as client:
        for url in _manga_url_candidates(manga_id):
            try:
                resp = client.get(url)
            except httpx.HTTPError as exc:
                last_error = f"request error for {url}: {exc}"
                continue
            if resp.status_code != 200:
                last_error = f"http status {resp.status_code} for {url}"
                continue
            html = resp.text
            if looks_blocked(html):
                last_error = f"blocked by anti-bot at {url}"
                continue

            soup = BeautifulSoup(html, "html.parser")
            title_el = soup.select_one("h1, h2")
            title = title_el.get_text(" ", strip=True) if title_el else "Manga"
            if "sorry, you have been blocked" in title.lower():
                last_error = f"title indicates anti-bot block at {url}"
                continue

            total_chapters = len(soup.select("a[href*='/capitulo-']"))

            cover_el = soup.select_one(
                ".cover-image, .series-cover, .manga-image picture img, .series-thumb img, img[src]"
            )
            cover_path = None
            if cover_el is not None:
                raw = cover_el.get("data-src") or cover_el.get("src") or cover_el.get("style")
                if raw:
                    if "url(" in raw:
                        m = re.search(r"url\((.*?)\)", raw)
                        raw = m.group(1).strip("'\"") if m else None
                    if raw:
                        cover_path = _to_abs(normalize_image_url(raw))

            synopsis_el = soup.select_one(".summary__content, .description-summary, p")
            synopsis = None
            if synopsis_el:
                text = synopsis_el.get_text(" ", strip=True)
                synopsis = text if len(text) > 20 else None

            return _mk_manga(url, title, cover_path, synopsis, total_chapters)

    raise RuntimeError(f"MangaLivre details failed: {last_error}")


_CHAPTER_SELECTOR_CHAIN = [
    "ul.full-chapters-list.list-of-chapters a[href]",
    "ul.list-of-chapters a[href]",
    "a[href*='/capitulo-']",
]
_IMAGE_SELECTOR_CHAIN = [
    "div.manga-image picture img",
    "div.manga-continue img",
    "img.wp-manga-chapter-img",
    ".reading-content img",
    ".entry-content img",
    "img[data-src]",
    "img[src]",
]


def _chapter_links_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    chapter_links: list[str] = []
    for sel in _CHAPTER_SELECTOR_CHAIN:
        found = [a["href"] for a in soup.select(sel) if a.get("href")]
        if found:
            chapter_links = found
            break
    if not chapter_links:
        chapter_links = extract_chapter_urls_from_text(html)
    return sorted(
        {_to_abs(link) for link in chapter_links},
        key=lambda u: chapter_number_from_url(u) or 0.0,
    )


def list_chapters(manga_url: str) -> list[MangaChapterOption]:
    last_error = "unknown error"
    with new_client(timeout=20) as client:
        for url in _manga_url_candidates(manga_url):
            try:
                resp = client.get(url)
            except httpx.HTTPError as exc:
                last_error = f"request error for {url}: {exc}"
                continue
            if resp.status_code != 200:
                last_error = f"http status {resp.status_code} for {url}"
                continue
            manga_html = resp.text
            if looks_blocked(manga_html):
                last_error = f"blocked by anti-bot at {url}"
                continue
            chapter_links = _chapter_links_from_html(manga_html)
            if chapter_links:
                return [
                    MangaChapterOption(index=idx, label=chapter_label(chapter_url, idx)[0], url=chapter_url)
                    for idx, chapter_url in enumerate(chapter_links, start=1)
                ]
            last_error = f"parsed 0 chapter links for {url}"
    raise RuntimeError(f"MangaLivre chapters failed: {last_error}")


def download_chapters(
    manga_url: str,
    dest: Path,
    chapters: str = "all",
    fmt: str = "cbz",
    on_progress: ProgressCallback | None = None,
) -> Manga:
    dest.mkdir(parents=True, exist_ok=True)
    fmt = fmt.strip().lower()
    root_url = _manga_root_url(manga_url)

    with new_client(timeout=25) as client:
        last_error = "unknown error"
        abs_links: list[str] = []
        manga_url = root_url
        for candidate in _manga_url_candidates(root_url):
            try:
                resp = client.get(candidate)
            except httpx.HTTPError as exc:
                last_error = f"request error for {candidate}: {exc}"
                continue
            if resp.status_code != 200:
                last_error = f"http status {resp.status_code} for {candidate}"
                continue
            manga_html = resp.text
            if looks_blocked(manga_html):
                last_error = f"blocked by anti-bot at {candidate}"
                continue
            abs_links = _chapter_links_from_html(manga_html)
            if abs_links:
                manga_url = candidate
                break
            last_error = f"parsed 0 chapter links for {candidate}"
        if not abs_links:
            raise RuntimeError(f"No chapter links found on MangaLivre page: {last_error}")

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
            if looks_blocked(ch_html):
                continue

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
                images = extract_image_urls_from_text(ch_html)

            images = [
                src
                for src in images
                if any(ext in src.lower() for ext in (".jpg", ".jpeg", ".png", ".webp"))
                and not src.lower().startswith("data:")
                and not any(marker in src.lower() for marker in _SKIP_MARKERS)
            ]
            if not images:
                continue

            chapter_dir = dest / f"chapter_{chapter_file_label}"
            chapter_dir.mkdir(parents=True, exist_ok=True)
            chapter_saved = 0
            for i, img_url in enumerate(images):
                abs_img = _to_abs(img_url)
                try:
                    resp = client.get(
                        abs_img,
                        headers={
                            "Referer": chapter_url,
                            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                        },
                    )
                    resp.raise_for_status()
                except httpx.HTTPError:
                    continue

                content_type = resp.headers.get("content-type", "").lower()
                if not content_type.startswith("image/"):
                    continue

                ext = guess_image_ext(abs_img)
                (chapter_dir / f"{i + 1:03d}.{ext}").write_bytes(resp.content)
                chapter_saved += 1
                total_saved_pages += 1

                if on_progress:
                    chapter_pct = int((i + 1) * 100 / len(images))
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
        raise RuntimeError(f"No pages were downloaded from MangaLivre ({len(selected)} selected chapters)")

    if on_progress:
        on_progress(100, "completed")

    return Manga(
        id=manga_url,
        title=title_from_folder(dest),
        source_id="mangalivre",
        source_name="Manga Livre",
        cover_path=find_cover_in_tree(dest),
        status="unknown",
        local_path=str(dest),
        total_chapters=total_chapters_with_pages,
        downloaded_chapters=total_chapters_with_pages,
    )


class MangaLivreSource(MangaSource):
    id = "mangalivre"
    name = "Manga Livre"

    def search(self, query: str, page: int = 1) -> tuple[list[Manga], int]:
        return search_paginated(query, page)

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
