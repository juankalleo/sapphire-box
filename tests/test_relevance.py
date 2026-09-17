"""core.relevance — the ranking step every "todas as fontes" search runs
through, so noise a source's own search hands back doesn't bury or hide
real matches once results get merged."""
from __future__ import annotations

from dataclasses import dataclass

from sapphirebox.core import relevance


def test_exact_match_scores_highest():
    assert relevance.score("Dom Casmurro", "Dom Casmurro") > relevance.score("Dom Casmurro e outros contos", "Dom Casmurro")


def test_unrelated_title_scores_zero():
    assert relevance.score("Fundamentos de Programação em R", "cabeça do santo") == 0.0


def test_accent_and_case_insensitive():
    assert relevance.score("A Cabeça do Santo", "cabeca do santo") > 0
    assert relevance.score("A CABEÇA DO SANTO", "Cabeça Do Santo") == 100.0 or relevance.score(
        "A CABEÇA DO SANTO", "Cabeça Do Santo"
    ) > 50


def test_partial_word_overlap_scores_lower_than_full_match():
    full = relevance.score("Harry Potter e a Pedra Filosofal", "harry potter")
    partial = relevance.score("Harry e seus amigos no acampamento", "harry potter")
    assert full > partial > 0


@dataclass
class _Item:
    title: str


def test_rank_drops_zero_score_and_sorts_best_first():
    items = [
        _Item("Fundamentos de Programação em R"),
        _Item("A Cabeça do Santo"),
        _Item("Respostas Bíblicas às Testemunhas de Jeová"),
    ]
    ranked = relevance.rank(items, "cabeça do santo")
    assert [i.title for i in ranked] == ["A Cabeça do Santo"]


def test_rank_is_noop_for_empty_query():
    items = [_Item("A"), _Item("B")]
    assert relevance.rank(items, "") == items
    assert relevance.rank(items, "   ") == items


def test_rank_keeps_relative_order_of_ties():
    """Two items with the same score keep source order — rank() must be
    a stable sort, not just "sort by score"."""
    items = [_Item("Harry Potter livro 1"), _Item("Harry Potter livro 2")]
    ranked = relevance.rank(items, "harry potter")
    assert [i.title for i in ranked] == [i.title for i in items]


def test_tolerates_a_missing_or_wrong_letter_per_word():
    """User report: typing "cabeça do satno" (transposed) or "cabesa do
    santo" (wrong letter) still has to find the real title — a single
    missing/extra/wrong character in a word (len >= 4) shouldn't zero out
    the whole word's contribution to the match."""
    assert relevance.score("A Cabeça do Santo", "cabeça do satno") > 0
    assert relevance.score("A Cabeça do Santo", "cabesa do santo") > 0
    assert relevance.score("Harry Potter e a Pedra Filosofal", "hary poter") > 0


def test_fuzzy_tolerance_does_not_match_unrelated_short_words():
    """The fuzzy fallback only kicks in for words long enough (>=4 chars)
    that a coincidental near-match is unlikely — short words like "do"
    must still require an exact (sub)string hit."""
    assert relevance.score("Introdução à Economia", "do") == 0.0


def test_reproduces_the_reported_elivros_bug():
    """The actual case from the field: eLivros' own /Search for "cabeça do
    santo" handed back ten unrelated titles and nothing about the real
    book — this is what merging + ranking must fix."""
    elivros_style_noise = [
        _Item("Pela Minha Janela"),
        _Item("Respostas Bíblicas às Testemunhas de Jeová"),
        _Item("Fundamentos de Programacao em R"),
    ]
    dlivros_style_hit = [_Item("A Cabeça do Santo"), _Item("A Palavra que Resta")]
    merged = elivros_style_noise + dlivros_style_hit
    ranked = relevance.rank(merged, "cabeça do santo")
    assert ranked[0].title == "A Cabeça do Santo"
    assert len(ranked) == 1


def test_is_probably_navigation_junk_catches_known_chrome():
    """Reported bug: browsing "Descobrir" surfaced genre/category nav
    links (a manga site's "Mangás"/"Manhwa" menu) and section headers as
    if they were real catalog items."""
    for junk in ["Mangás", "MANHWA", "webtoons", "Ver Todos os Destaques", "Mangá (89)", "  "]:
        assert relevance.is_probably_navigation_junk(junk), f"{junk!r} should be flagged as junk"


def test_is_probably_navigation_junk_leaves_real_titles_alone():
    for real in ["One Piece", "A Cabeça do Santo", "Mangá do Fim do Mundo", "PPPPPP"]:
        assert not relevance.is_probably_navigation_junk(real), f"{real!r} should NOT be flagged as junk"


def test_is_probably_navigation_junk_catches_seo_site_titles():
    assert relevance.is_probably_navigation_junk("Manga Livre - Leia Mangás, Manhwas e Manhuas Grátis em Português")


def test_dedupe_by_title_keeps_first_occurrence():
    items = [_Item("One Piece"), _Item("Naruto"), _Item("ONE PIECE"), _Item("one piece")]
    deduped = relevance.dedupe_by_title(items)
    assert [i.title for i in deduped] == ["One Piece", "Naruto"]


def test_clean_listing_drops_junk_and_duplicates_together():
    """Reported bug, reproduced end to end: a browse-mode listing mixing
    real manga with nav chrome and a repeated title."""
    items = [
        _Item("Mangás"),
        _Item("One Piece"),
        _Item("Manhwa"),
        _Item("Naruto"),
        _Item("One Piece"),
        _Item("Ver Todos os Destaques"),
    ]
    cleaned = relevance.clean_listing(items)
    assert [i.title for i in cleaned] == ["One Piece", "Naruto"]
