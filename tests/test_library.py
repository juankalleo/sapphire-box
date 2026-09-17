"""Library scan (folder -> Manga) and SQLite repository round-trips."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from sapphirebox.core import db
from sapphirebox.core.models import Book, DownloadJob, Manga
from sapphirebox.library import repository
from sapphirebox.manga import library as manga_library
from sapphirebox.web import reader as reader_service


@pytest.fixture()
def fresh_db(tmp_path):
    db.reset_connection()
    db.get_connection(tmp_path / "test.db")
    yield
    db.reset_connection()


def _write_index(manga_dir, **overrides):
    manga_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": "one-piece",
        "title": "One Piece",
        "authors": ["Eiichiro Oda"],
        "rating": 4.9,
        "state": "ongoing",
        "chapters": {"1": {"number": 1, "volume": 1, "date": "", "scanlator": "", "filename": "1.cbz"}},
        "app_version": "sapphirebox",
    }
    meta.update(overrides)
    (manga_dir / "index.json").write_text(json.dumps(meta), encoding="utf-8")


def test_scan_library_finds_manga_from_index_json(tmp_path):
    _write_index(tmp_path / "one-piece")
    (tmp_path / "not-a-manga.txt").write_text("noise")

    results = manga_library.scan_library(tmp_path)

    assert len(results) == 1
    manga = results[0]
    assert manga.id == "one-piece"
    assert manga.title == "One Piece"
    assert manga.total_chapters == 1
    assert manga.source_id == "local"


def test_scan_library_skips_manga_folder_without_index(tmp_path):
    (tmp_path / "no-index").mkdir()
    assert manga_library.scan_library(tmp_path) == []


def test_scan_library_creates_missing_root(tmp_path):
    missing = tmp_path / "does-not-exist-yet"
    assert manga_library.scan_library(missing) == []
    assert missing.exists()


def test_manga_repository_upsert_and_search(fresh_db):
    manga = Manga(id="m1", title="Solo Leveling", source_id="niadd", source_name="Niadd", local_path="/tmp/m1")
    repository.upsert_manga(manga)

    found = repository.get_manga_by_id("m1")
    assert found is not None
    assert found.title == "Solo Leveling"

    results = repository.search_by_title("Solo")
    assert len(results) == 1

    manga.title = "Solo Leveling (updated)"
    repository.upsert_manga(manga)
    assert repository.get_manga_by_id("m1").title == "Solo Leveling (updated)"


def test_book_repository_upsert_and_list(fresh_db):
    book = Book(
        id="gutenberg-1",
        title="Dom Casmurro",
        source_id="gutenberg",
        source_name="Project Gutenberg",
        local_path="/tmp/dom-casmurro.epub",
    )
    repository.upsert_book(book)

    items, total_pages = repository.list_downloaded_books()
    assert total_pages == 1
    assert [b.id for b in items] == ["gutenberg-1"]


def test_unified_library_endpoint_treats_empty_kind_as_all(fresh_db):
    """Regression: the browser always sends `kind=` in the query string
    (never omits it), which FastAPI binds as "" — not None. The endpoint
    used to check `kind in (None, "manga")`, so an explicit empty string
    matched neither branch and silently returned zero items."""
    from sapphirebox.web.server import library

    repository.upsert_manga(Manga(id="m1", title="Solo Leveling", source_id="niadd", source_name="Niadd", local_path="/tmp/m1"))
    repository.upsert_book(Book(id="b1", title="Dom Casmurro", source_id="gutenberg", source_name="Gutenberg", local_path="/tmp/b1.epub"))

    result = library(kind="")
    assert result["total"] == 2

    result_omitted = library()
    assert result_omitted["total"] == 2

    result_manga_only = library(kind="manga")
    assert result_manga_only["total"] == 1
    assert result_manga_only["items"][0]["kind"] == "manga"


def test_manga_details_preserves_downloaded_local_path(fresh_db, monkeypatch):
    from sapphirebox.manga import manager as manga_manager

    class FakeSource:
        def get_details(self, manga_id):
            return Manga(id=manga_id, title="Solo Leveling remoto", source_id="niadd", source_name="Niadd")

        def list_chapters(self, manga_id):
            return []

    repository.upsert_manga(
        Manga(
            id="m1",
            title="Solo Leveling",
            source_id="niadd",
            source_name="Niadd",
            local_path="/tmp/m1",
            total_chapters=12,
            downloaded_chapters=3,
        )
    )
    monkeypatch.setattr(manga_manager.registry, "get_source", lambda source_id: FakeSource())

    detailed = manga_manager.get_details("niadd", "m1")
    saved = repository.get_manga_by_id("m1")

    assert detailed is not None
    assert detailed.local_path == "/tmp/m1"
    assert detailed.total_chapters == 12
    assert detailed.downloaded_chapters == 3
    assert saved is not None
    assert saved.local_path == "/tmp/m1"


def test_book_archive_reader_reads_cbz_pages(fresh_db, tmp_path):
    cbz_path = tmp_path / "comic.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        zf.writestr("page_002.jpg", b"two")
        zf.writestr("page_001.png", b"one")
        zf.writestr("notes.txt", b"ignore")

    repository.upsert_book(
        Book(
            id="comic-1",
            title="Comic",
            source_id="zonafantasma",
            source_name="Zona Fantasma",
            format="cbz",
            local_path=str(cbz_path),
        )
    )

    pages = reader_service.list_book_archive_pages("comic-1")

    assert pages == ["page_001.png", "page_002.jpg"]
    assert reader_service.read_book_archive_page("comic-1", "page_001.png") == b"one"


def test_delete_library_item_removes_book_file_and_db(fresh_db, tmp_path, monkeypatch):
    from sapphirebox.web import server

    library_root = tmp_path / "library"
    books_root = tmp_path / "books"
    library_root.mkdir()
    books_root.mkdir()
    book_path = tmp_path / "dom.epub"
    book_path.write_bytes(b"book")
    repository.upsert_book(
        Book(
            id="book-1",
            title="Dom Casmurro",
            source_id="bdebooks",
            source_name="BDeBooks",
            format="epub",
            local_path=str(book_path),
        )
    )
    monkeypatch.setattr(server.config, "get_library_path", lambda: library_root)
    monkeypatch.setattr(server.config, "get_books_library_path", lambda: books_root)

    result = server.delete_library_item(kind="book", item_id="book-1")

    assert result["ok"] is True
    assert not book_path.exists()
    assert repository.get_book_by_id("book-1") is None


def test_clear_downloaded_library_removes_files_and_db(fresh_db, tmp_path, monkeypatch):
    from sapphirebox.web import server

    manga_root = tmp_path / "library"
    books_root = tmp_path / "books"
    manga_dir = manga_root / "m1"
    manga_dir.mkdir(parents=True)
    (manga_dir / "chapter_1.cbz").write_bytes(b"cbz")
    orphan = manga_root / "orphan.tmp"
    orphan.write_bytes(b"orphan")
    books_root.mkdir()
    book_path = books_root / "book.epub"
    book_path.write_bytes(b"book")

    repository.upsert_manga(
        Manga(id="m1", title="Manga", source_id="local", source_name="Local", local_path=str(manga_dir))
    )
    repository.upsert_book(
        Book(id="b1", title="Book", source_id="bdebooks", source_name="BDeBooks", local_path=str(book_path))
    )
    monkeypatch.setattr(server.config, "get_library_path", lambda: manga_root)
    monkeypatch.setattr(server.config, "get_books_library_path", lambda: books_root)

    result = server.clear_downloaded_library()

    assert result["ok"] is True
    assert not manga_dir.exists()
    assert not orphan.exists()
    assert not book_path.exists()
    assert repository.list_library()[0] == []
    assert repository.list_downloaded_books()[0] == []


def test_import_latest_manual_download_moves_file_to_books_library(fresh_db, tmp_path, monkeypatch):
    from sapphirebox.web import downloads

    downloads_dir = tmp_path / "Downloads"
    downloads_dir.mkdir()
    downloaded_file = downloads_dir / "Batman.cbr"
    downloaded_file.write_bytes(b"comic")
    books_root = tmp_path / "books"
    monkeypatch.setattr(downloads.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(downloads.config, "get_books_library_path", lambda: books_root)
    job = DownloadJob(
        id="job-1",
        status="manual_required",
        domain="book",
        source_id="multiversohq",
        source_name="Multiverso HQ",
        item_id="https://multiversohq.com/batman-1/",
        title="Batman #1",
        format="cbr",
        manual_url="https://workupload.com/file/xyz",
    )

    book = downloads.import_latest_manual_download(job)

    assert not downloaded_file.exists()
    assert book.local_path is not None
    assert book.local_path.endswith("Batman #1.cbr")
    assert Path(book.local_path).read_bytes() == b"comic"
    saved = repository.get_book_by_id("https://multiversohq.com/batman-1/")
    assert saved is not None
    assert saved.source_id == "multiversohq"


# --- reading_state (retoma de onde parou) -----------------------------------


def test_reading_state_round_trips_for_manga(fresh_db):
    assert repository.get_reading_state("one-piece") is None

    repository.save_reading_state("one-piece", "manga", chapter_file="chapter_12.cbz", page_index=4)
    state = repository.get_reading_state("one-piece")
    assert state == {
        "itemId": "one-piece",
        "kind": "manga",
        "chapterFile": "chapter_12.cbz",
        "pageIndex": 4,
        "location": None,
    }


def test_reading_state_round_trips_for_epub_location(fresh_db):
    repository.save_reading_state("dom-casmurro", "epub", location="epubcfi(/6/14!/4/2/2/2/1:0)")
    state = repository.get_reading_state("dom-casmurro")
    assert state["kind"] == "epub"
    assert state["location"] == "epubcfi(/6/14!/4/2/2/2/1:0)"
    assert state["chapterFile"] is None
    assert state["pageIndex"] is None


def test_save_reading_state_upserts_instead_of_duplicating(fresh_db):
    repository.save_reading_state("naruto", "manga", chapter_file="chapter_1.cbz", page_index=0)
    repository.save_reading_state("naruto", "manga", chapter_file="chapter_1.cbz", page_index=7)
    repository.save_reading_state("naruto", "manga", chapter_file="chapter_2.cbz", page_index=1)

    state = repository.get_reading_state("naruto")
    assert state["chapterFile"] == "chapter_2.cbz"
    assert state["pageIndex"] == 1


def test_delete_reading_state_removes_the_row(fresh_db):
    repository.save_reading_state("naruto", "manga", chapter_file="chapter_1.cbz", page_index=0)
    repository.delete_reading_state("naruto")
    assert repository.get_reading_state("naruto") is None


def test_delete_all_reading_state_clears_everything(fresh_db):
    repository.save_reading_state("naruto", "manga", chapter_file="chapter_1.cbz", page_index=0)
    repository.save_reading_state("one-piece", "manga", chapter_file="chapter_1.cbz", page_index=0)
    repository.delete_all_reading_state()
    assert repository.get_reading_state("naruto") is None
    assert repository.get_reading_state("one-piece") is None


def test_reading_state_endpoint_round_trip(fresh_db):
    from sapphirebox.web.server import get_reading_state as get_endpoint
    from sapphirebox.web.server import save_reading_state as save_endpoint

    assert get_endpoint(id="solo-leveling")["state"] is None

    save_endpoint({"id": "solo-leveling", "kind": "manga", "chapterFile": "chapter_3.cbz", "pageIndex": 2})
    result = get_endpoint(id="solo-leveling")["state"]
    assert result["chapterFile"] == "chapter_3.cbz"
    assert result["pageIndex"] == 2
