"""Relevance scoring shared by every search aggregator.

The concrete bug this fixes: eLivros' own `/Search` endpoint doesn't
return an empty list when it has nothing good — it falls back to some
unrelated "browse" set instead. Concatenating that straight into merged
"todas as fontes" results buried real matches (or drowned them out
entirely) behind ten unrelated titles. Every manager that merges results
across sources runs them through here first: score against the query,
drop the zero-relevance noise, sort the rest best-first.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

_FUZZY_MIN_WORD_LEN = 4
_FUZZY_RATIO = 0.8

# Browse/listing pages (a homepage, a "hot" or "recent" widget) mix real
# items in with site chrome — genre/category nav links, section headers,
# the page's own <title> — that scraping can't always tell apart from a
# real card by markup alone. These are the exact strings caught in the
# field (Portuguese manga/manhwa/quadrinho sites); matched only after
# normalize(), so accents/case don't matter.
_JUNK_TITLES = {
    "manga", "mangas", "manhwa", "manhwas", "manhua", "manhuas",
    "webtoon", "webtoons", "novel", "novels", "quadrinho", "quadrinhos",
    "hq", "hqs", "livro", "livros", "genero", "generos", "categoria",
    "categorias", "populares", "populares agora", "recentes",
    "lancamentos", "novidades", "destaques", "em alta", "mais lidos",
    "recem adicionados", "ver todos os destaques", "ver todos os mangas",
    "ver mais", "carregar mais", "todos", "todas as fontes", "inicio",
    "home", "menu", "voltar",
}
_JUNK_BADGE_RE = re.compile(r"\(\s*\d+\s*\)\s*$")


def is_probably_navigation_junk(title: str) -> bool:
    """True for a parsed "item" that's actually page chrome, not a real
    manga/book/comic — a genre link, a section header, a "(89)" counter
    badge, or the page's own SEO title, all of which browse-mode scraping
    can pick up because they share markup with the real cards."""
    n = normalize(title)
    n = _JUNK_BADGE_RE.sub("", n).strip()
    if not n:
        return True
    if n in _JUNK_TITLES:
        return True
    if " - " in n and any(kw in n for kw in ("leia", "gratis", "ler online", "baixar", "download")):
        return True
    return False


def dedupe_by_title(items: list, title_of=lambda item: item.title) -> list:
    """Keeps the first occurrence of each normalized title — a browse page
    often lists the same item twice (a "recent" rail and a "popular" rail
    both featuring it, or two sources' cards merged together)."""
    seen: set[str] = set()
    out = []
    for item in items:
        key = normalize(title_of(item))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def clean_listing(items: list, title_of=lambda item: item.title) -> list:
    """Drops nav/genre junk and duplicate titles from a raw listing.
    Unlike rank(), this isn't query-dependent — it runs on every listing,
    search or browse, since scraping a homepage/catalog page routinely
    surfaces menu links and repeated cards that a clean search-results
    page wouldn't."""
    filtered = [it for it in items if not is_probably_navigation_junk(title_of(it))]
    return dedupe_by_title(filtered, title_of)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower().strip()


def _word_matches(query_word: str, title_n: str, title_words: list[str]) -> bool:
    """Exact substring against the full title, or — for words long enough
    that a coincidence is unlikely — a fuzzy match against one of the
    title's own words, so a missing/extra/wrong letter (a typo, or an
    accent typed as a plain letter that normalize() didn't already fix)
    still counts instead of silently scoring 0. Fuzzy is deliberately
    one-directional (query word vs. whole title words, never the other
    way) — matching short title words like "a"/"de" against *any* longer
    query word would trivially "match" almost everything."""
    if query_word in title_n:
        return True
    if len(query_word) < _FUZZY_MIN_WORD_LEN:
        return False
    return any(difflib.SequenceMatcher(None, query_word, tw).ratio() >= _FUZZY_RATIO for tw in title_words)


def score(title: str, query: str) -> float:
    """Higher is more relevant. 0 means "not a real match" — safe to drop
    when merging results a source's own search handed back as noise."""
    query = query.strip()
    if not query:
        return 1.0

    title_n = normalize(title)
    query_n = normalize(query)

    if title_n == query_n:
        return 100.0
    if title_n.startswith(query_n):
        return 80.0
    if query_n in title_n:
        return 60.0

    words = [w for w in query_n.split() if len(w) > 1]
    if not words:
        return 0.0
    title_words = title_n.split()
    matched = sum(1 for w in words if _word_matches(w, title_n, title_words))
    if matched == 0:
        return 0.0
    return 20.0 * (matched / len(words))


def rank(items: list, query: str, title_of=lambda item: item.title) -> list:
    """Drops zero-relevance items and sorts the rest best-match-first.
    Stable otherwise, so items tied on score keep whatever order the
    source(s) returned them in."""
    if not query.strip():
        return items
    scored = [(score(title_of(item), query), item) for item in items]
    return [item for s, item in sorted(scored, key=lambda pair: pair[0], reverse=True) if s > 0]


def best_score(items: list, query: str, title_of=lambda item: item.title) -> float:
    """The highest score() among `items` against `query`, or 0.0 for an
    empty list. Used to judge *how* confident a match is — not just
    whether one exists — since a weak coincidental word-overlap hit
    (score 10-20) shouldn't be treated the same as a real one."""
    if not items:
        return 0.0
    return max(score(title_of(item), query) for item in items)


def widen_query_candidates(query: str, max_variants: int = 6) -> list[str]:
    """Progressively shorter variants of `query`, to retry a source's
    search with when the exact query came back as pure noise. Trims from
    the end first (a remote site's own search often fails on a typo'd or
    over-specific trailing word — "cabeca do satno" — even though it
    handles the shorter phrase — "cabeca do" — just fine), then from the
    front: a title's most distinctive word isn't always the last one
    typed ("ensaio cegueira" only finds "Ensaio Sobre a Cegueira" via the
    word "cegueira" alone, which trimming from the end never reaches).
    We can't fix a typo or a misordered query we don't know is one, but
    we can retry with less of it and let `rank()` judge the extra
    candidates against what the user actually typed."""
    words = query.strip().split()
    n = len(words)
    if n <= 1:
        return []

    seen = {query.strip()}
    variants: list[str] = []

    def add(candidate: str) -> None:
        if candidate and candidate not in seen:
            seen.add(candidate)
            variants.append(candidate)

    trimmed = words[:]
    for _ in range(n - 1):
        trimmed = trimmed[:-1]
        add(" ".join(trimmed))

    trimmed = words[:]
    for _ in range(n - 1):
        trimmed = trimmed[1:]
        add(" ".join(trimmed))

    return variants[:max_variants]
