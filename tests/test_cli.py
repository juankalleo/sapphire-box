from __future__ import annotations

from sapphirebox.cli import app as cli_app


def test_detects_manga_source_from_url():
    assert cli_app._detect_source("https://mangalivre.to/manga/one-piece/") == (
        "manga",
        "mangalivre",
        "Manga Livre",
    )


def test_detects_book_source_from_url():
    assert cli_app._detect_source("https://www.baixelivros.com.br/literatura/dom-casmurro") == (
        "book",
        "baixelivros",
        "Baixe Livros",
    )


def test_extracts_special_book_ids_from_url():
    assert cli_app._book_id_from_url("gutenberg", "https://www.gutenberg.org/ebooks/55752") == "gutenberg-55752"
    assert cli_app._book_id_from_url("internet_archive", "https://archive.org/details/domcasmurro00assi") == (
        "ia-domcasmurro00assi"
    )

