"""Parser/logic tests that don't touch the network — the actual scraping
functions are exercised manually against the live sites (see README);
what matters here is that HTML we know the shape of still parses the way
the old Rust scraper did.
"""
from __future__ import annotations

from sapphirebox.manga.sources import mangalivre, niadd
from sapphirebox.manga.sources.base import chapter_label, chapter_number_from_url, parse_requested_chapters

MANGALIVRE_SERIES_LIST_HTML = """
<html><body>
<ul class="seriesList">
  <li>
    <a href="/manga/one-piece/">
      <img data-src="//img.example.com/one-piece.jpg" />
    </a>
    <span class="series-title">One Piece</span>
    <p class="series-desc">Um pirata de borracha procura um tesouro lendario.</p>
    <span class="series-chapters">1099 capitulos</span>
  </li>
  <li>
    <a href="/manga/naruto/capitulo-1/">
      <span class="series-title">Naruto (capitulo)</span>
    </a>
  </li>
</ul>
</body></html>
"""

NIADD_LIST_HTML = """
<html><body>
<div class="list-item">
  <a href="/manga/solo-leveling.html">
    <div class="manga-img"><img data-src="//cdn.example.com/solo-leveling.jpg" /></div>
  </a>
</div>
<a href="/manga/solo-leveling.html" title="Solo Leveling">Solo Leveling</a>
<a href="/manga/.html">placeholder</a>
</body></html>
"""


def test_mangalivre_parses_serieslist_and_skips_chapter_links():
    results = mangalivre._parse_cards(MANGALIVRE_SERIES_LIST_HTML, "")
    assert len(results) == 1
    manga = results[0]
    assert manga.title == "One Piece"
    assert manga.id == "https://mangalivre.to/manga/one-piece/"
    assert manga.cover_path == "https://img.example.com/one-piece.jpg"
    assert manga.total_chapters == 1099
    assert "pirata" in manga.synopsis


def test_mangalivre_query_filters_by_title():
    results = mangalivre._parse_cards(MANGALIVRE_SERIES_LIST_HTML, "piece")
    assert len(results) == 1
    results_miss = mangalivre._parse_cards(MANGALIVRE_SERIES_LIST_HTML, "bleach")
    assert results_miss == []


MANGALIVRE_MADARA_CATALOG_HTML = """
<html><body>
<div class="page-item-detail manga">
  <div class="item-thumb"><a href="https://mangalivre.to/manga/one-piece-ptbr/">
    <img src="https://img.example.com/one-piece.jpg" />
  </a></div>
  <div class="item-summary">
    <div class="post-title font-title"><h3 class="h5">
      <a href="https://mangalivre.to/manga/one-piece-ptbr/">One Piece</a>
    </h3></div>
    <div class="author meta"><a href="https://mangalivre.to/manga-author/eiichiro-oda/" rel="tag">Eiichiro Oda</a></div>
    <div class="list-chapter">
      <div class="chapter-item"><span class="chapter font-meta">
        <a href="https://mangalivre.to/manga/one-piece-ptbr/capitulo-1190/" class="btn-link">Capitulo 1190</a>
      </span></div>
    </div>
  </div>
</div>
</body></html>
"""


def test_mangalivre_madara_catalog_skips_author_and_chapter_links():
    """Real bug from the field: the old fallback selector was broad enough
    (".page-item-detail a") to also pick up the card's own author link and
    chapter links as if each were a separate manga ("Eiichiro Oda" and
    "Capitulo 1190" showing up as titles in Descobrir)."""
    results = mangalivre._parse_cards(MANGALIVRE_MADARA_CATALOG_HTML, "")
    assert [m.title for m in results] == ["One Piece"]
    assert results[0].cover_path == "https://img.example.com/one-piece.jpg"


def test_mangalivre_extracts_sorted_unique_chapter_links():
    html = """
    <a href="/manga/one-piece/capitulo-10/">Capitulo 10</a>
    <a href="https://mangalivre.to/manga/one-piece/capitulo-2/">Capitulo 2</a>
    <a href="/manga/one-piece/capitulo-10/">duplicado</a>
    """

    assert mangalivre._chapter_links_from_html(html) == [
        "https://mangalivre.to/manga/one-piece/capitulo-2/",
        "https://mangalivre.to/manga/one-piece/capitulo-10/",
    ]


def test_mangalivre_prefers_to_mirror_for_cached_tv_urls():
    assert mangalivre._manga_url_candidates("https://mangalivre.tv/manga/one-piece-ptbr/")[:2] == [
        "https://mangalivre.to/manga/one-piece-ptbr/",
        "https://mangalivre.tv/manga/one-piece-ptbr/",
    ]


def test_niadd_parses_cards_and_skips_placeholder():
    results = niadd._parse_cards(NIADD_LIST_HTML, "")
    ids = [m.id for m in results]
    assert "https://br.niadd.com/manga/solo-leveling.html" in ids
    assert not any(i.endswith("/manga/.html") for i in ids)
    manga = next(m for m in results if m.id.endswith("solo-leveling.html"))
    assert manga.cover_path == "https://cdn.example.com/solo-leveling.jpg"


def test_niadd_extracts_unique_chapter_links_in_page_order():
    html = """
    <a class="chapter-item" href="/manga/solo-leveling/chapter-3">3</a>
    <a class="chapter-item" href="/manga/solo-leveling/chapter-2">2</a>
    <a class="chapter-item" href="/manga/solo-leveling/chapter-3">duplicado</a>
    """

    assert niadd._chapter_links_from_html(html) == [
        "https://br.niadd.com/manga/solo-leveling/chapter-3",
        "https://br.niadd.com/manga/solo-leveling/chapter-2",
    ]


def test_niadd_normalize_url_strips_chapter_suffix():
    chapter_url = "https://br.niadd.com/manga/solo-leveling/chapter-12"
    assert niadd.normalize_niadd_url(chapter_url) == "https://br.niadd.com/manga/solo-leveling"


def test_niadd_normalize_url_keeps_root_html_page_untouched():
    # Root pages on Niadd are themselves "<slug>.html" — the .html branch
    # matches first, so a root URL (no chapter marker) passes through as-is.
    root_url = "https://br.niadd.com/manga/solo-leveling.html"
    assert niadd.normalize_niadd_url(root_url) == root_url


def test_chapter_number_and_label_from_url():
    assert chapter_number_from_url("https://x/manga/y/capitulo-12/") == 12.0
    assert chapter_number_from_url("https://x/manga/y/capitulo-12.5/") == 12.5
    assert chapter_number_from_url("https://x/manga/y/") is None

    assert chapter_label("https://x/capitulo-12/", fallback_idx=1) == ("12", "12")
    assert chapter_label("https://x/capitulo-12.5/", fallback_idx=1) == ("12.5", "12_5")
    assert chapter_label("https://x/no-number/", fallback_idx=7) == ("7", "7")


def test_parse_requested_chapters():
    assert parse_requested_chapters("all", 5) == [1, 2, 3, 4, 5]
    assert parse_requested_chapters("", 5) == [1, 2, 3, 4, 5]
    assert parse_requested_chapters("1-3", 10) == [1, 2, 3]
    assert parse_requested_chapters("1,3,7", 10) == [1, 3, 7]
    assert parse_requested_chapters("1,3,99", 5) == [1, 3, 5]
    assert parse_requested_chapters("not-a-number", 5) == [1]
