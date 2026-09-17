"""books.manager — query widening, the part of the "cabeça do santo" fix
that isn't just relevance scoring: retrying a bad query with a shorter
version of itself when a source's own search comes back as pure noise.
No network calls — everything runs against a fake BookSource."""
from __future__ import annotations

from sapphirebox.books.manager import _search_raw_with_widening
from sapphirebox.core.models import Book


class _FakeSource:
    def __init__(self, responses: dict[str, list[Book]]):
        self.id = "fake"
        self.name = "Fake"
        self._responses = responses
        self.calls: list[str] = []

    def search(self, query: str, limit: int = 20, page: int = 1) -> list[Book]:
        self.calls.append(query)
        return list(self._responses.get(query, []))


def _book(title: str) -> Book:
    return Book(id=title, title=title, source_id="fake", source_name="Fake")


def test_widens_when_exact_query_is_pure_noise():
    """"cabeca do satno" (typo on "santo") finds nothing on the source's
    own search, but "cabeca do" (one word dropped) does — the widened
    result has to surface even though the user never typed it."""
    source = _FakeSource({
        "cabeca do satno": [_book("Título Qualquer"), _book("Outro Sem Relação")],
        "cabeca do": [_book("A Cabeça do Santo")],
    })
    results = _search_raw_with_widening(source, "cabeca do satno", limit=20)
    assert any(b.title == "A Cabeça do Santo" for b in results)
    assert source.calls == ["cabeca do satno", "cabeca do"]


def test_does_not_widen_when_exact_query_already_ranks():
    source = _FakeSource({"harry potter": [_book("Harry Potter e a Pedra Filosofal")]})
    results = _search_raw_with_widening(source, "harry potter", limit=20)
    assert [b.title for b in results] == ["Harry Potter e a Pedra Filosofal"]
    assert source.calls == ["harry potter"]


def test_stops_widening_as_soon_as_a_variant_is_fully_confident():
    """Three-word query (reordered vs. the real title); the first widened
    variant's results already contain every one of the original query's
    words — that's a confident (score 20, full word-overlap) match, so
    widening must stop right there instead of trying the weaker variants
    still queued up after it."""
    source = _FakeSource({
        "potter harry filosofal": [],
        "potter harry": [_book("Harry Potter e a Pedra Filosofal")],
        "potter": [_book("Unrelated Potter Book")],
    })
    results = _search_raw_with_widening(source, "potter harry filosofal", limit=20)
    assert any(b.title == "Harry Potter e a Pedra Filosofal" for b in results)
    assert source.calls == ["potter harry filosofal", "potter harry"]


def test_keeps_widening_past_a_weak_coincidental_partial_match():
    """Regression: the field bug behind this whole widening mechanism.
    "ensaio" alone in "ensaio cegueira" coincidentally overlaps an
    unrelated book's title (score 10 — only one of two words matches),
    which used to be (wrongly) treated as "good enough" and stopped the
    search before it ever tried "cegueira" — the word that actually finds
    "Ensaio Sobre a Cegueira"."""
    source = _FakeSource({
        "ensaio cegueira": [_book("Dentro da Baleia e Outros Ensaios")],
        "ensaio": [_book("Dentro da Baleia e Outros Ensaios")],
        "cegueira": [_book("Ensaio Sobre a Cegueira")],
    })
    results = _search_raw_with_widening(source, "ensaio cegueira", limit=20)
    assert any(b.title == "Ensaio Sobre a Cegueira" for b in results)
    assert "cegueira" in source.calls


def test_does_not_widen_a_single_word_query():
    """Nothing shorter to try — widen_query_candidates("cabeca") is empty,
    so a lone generic word that finds nothing stays exactly that: a
    real, disclosed limitation of the remote source's own search, not
    something client-side retrying can paper over."""
    source = _FakeSource({"cabeca": [_book("Noise")]})
    _search_raw_with_widening(source, "cabeca", limit=20)
    assert source.calls == ["cabeca"]


def test_does_not_widen_browse_mode_or_paged_requests():
    source = _FakeSource({})
    _search_raw_with_widening(source, "", limit=20, page=1)
    _search_raw_with_widening(source, "something", limit=20, page=2)
    assert source.calls == ["", "something"]
