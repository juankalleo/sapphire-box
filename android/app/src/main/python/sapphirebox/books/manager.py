"""Orchestration for the books module — the books/ counterpart of
manga/manager.py. Every book source is plain Python, portable to
Linux/Android as-is.
"""
from __future__ import annotations

from pathlib import Path

from sapphirebox.books.sources import registry
from sapphirebox.core import relevance
from sapphirebox.core.config import get_books_library_path
from sapphirebox.core.models import Book
from sapphirebox.library import repository

# eLivros/Dlivros ignore the `page` argument (their "browse" fallback is a
# single static listing), so claiming a next page for them would just show
# the same items again forever — only sources that actually paginate are
# allowed to report "there's more" in the total_pages estimate below.
_PAGINATED_SOURCES = {"baixelivros", "bdebooks", "libgen", "zonafantasma", "multiversohq", "gutenberg", "internet_archive"}

# score()'s word-overlap tier tops out at exactly 20.0 (every query word
# found in the title); anything below that means only *some* of the query
# words matched — e.g. "ensaio cegueira" scores 10 against "Dentro da
# Baleia e Outros Ensaios" (just "ensaio" overlaps) purely by coincidence.
# Widening must keep trying variants past a weak partial hit like that, or
# it never reaches the variant ("cegueira" alone) that actually finds the
# real book. 20.0 (full overlap) or 60+ (a real substring/exact match) are
# both "good enough to stop"; anything in between doesn't exist.
_CONFIDENT_SCORE = 20.0


def _search_raw_with_widening(source, query: str, limit: int, page: int = 1) -> list[Book]:
    """Fetches raw (unranked) results for `query`, and — only when that
    exact query doesn't come back with a confident match — retries with
    progressively shorter variants of it, merging whatever each attempt
    returns, until a confident one turns up or variants run out. This is
    for queries a source's own search chokes on outright (an extra,
    misspelled, or misplaced word), not for ranking; the caller still
    ranks the merged pool against the original `query` before showing
    anything. Paging and browse mode (empty query) never widen — there's
    no "exact query found nothing good" signal to react to in either
    case."""
    try:
        results = source.search(query, limit, page)
    except Exception:
        results = []

    if page > 1 or not query.strip() or relevance.best_score(results, query) >= _CONFIDENT_SCORE:
        return results

    for variant in relevance.widen_query_candidates(query):
        try:
            extra = source.search(variant, limit, page)
        except Exception:
            continue
        results = results + extra
        if relevance.best_score(results, query) >= _CONFIDENT_SCORE:
            break
    return results


def search(
    query: str,
    source_id: str | None = None,
    limit: int = 20,
    category: str | None = None,
    page: int = 1,
) -> tuple[list[Book], int]:
    """Some sources (eLivros in particular) hand back an unrelated "browse"
    list instead of an empty one when their own search finds nothing good —
    ranking by relevance and dropping zero-score items keeps that noise
    from burying (or outright hiding) the actual match, especially once
    results from several sources get merged together. When even that noise
    doesn't contain a real hit, `_search_raw_with_widening` retries with a
    shorter version of the query before giving up.

    Returns (results, total_pages). Paging only makes sense against a
    single named source — most of these sites don't expose an exact result
    count, so total_pages is a lower-bound estimate (current + 1 whenever
    a full page comes back)."""
    if source_id:
        source = registry.get_source(source_id)
        if source is None:
            return [], 1
        results = _search_raw_with_widening(source, query, limit, page)
        results = relevance.clean_listing(results)
        results = relevance.rank(results, query)
        has_more = source_id in _PAGINATED_SOURCES and len(results) >= limit
        total_pages = page + 1 if has_more else max(page, 1)
        return results[:limit], total_pages

    results: list[Book] = []
    for info in registry.list_enabled(category):
        source = registry.get_source(info.id)
        if source is None:
            continue
        results.extend(_search_raw_with_widening(source, query, limit))
    results = relevance.clean_listing(results)
    results = relevance.rank(results, query)
    return results[:limit], 1


def download(book: Book, dest_dir: Path | None = None, on_progress=None) -> Book:
    source = registry.get_source(book.source_id)
    if source is None:
        raise RuntimeError(f"Unknown or unimplemented book source '{book.source_id}'")

    dest_dir = dest_dir or get_books_library_path()
    book = source.download(book, dest_dir, on_progress)
    repository.upsert_book(book)
    return book


def get_details(book: Book) -> Book:
    source = registry.get_source(book.source_id)
    if source is None:
        return book
    return source.get_details(book)


def list_library(page: int = 1, page_size: int = 20) -> tuple[list[Book], int]:
    return repository.list_downloaded_books(page, page_size)
