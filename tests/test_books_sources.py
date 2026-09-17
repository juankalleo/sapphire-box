"""Pure-logic tests for the books module — no network calls."""
from __future__ import annotations

import pytest

from sapphirebox.books.sources import baixelivros, bdebooks, direct_files, gutenberg, internet_archive, libgen, multiverso_hq, zona_fantasma
from sapphirebox.books.sources.base import ManualDownloadRequired
from sapphirebox.core.cache import cache
from sapphirebox.core.models import Book


def test_gutenberg_prefers_epub_over_txt():
    formats = {
        "text/plain; charset=utf-8": "https://gutenberg.org/1.txt",
        "application/epub+zip": "https://gutenberg.org/1.epub",
        "image/jpeg": "https://gutenberg.org/1.jpg",
    }
    assert gutenberg._best_format(formats) == ("https://gutenberg.org/1.epub", "epub")
    assert gutenberg._cover_url(formats) == "https://gutenberg.org/1.jpg"


def test_gutenberg_falls_back_to_txt_when_no_epub():
    formats = {"text/plain; charset=utf-8": "https://gutenberg.org/2.txt"}
    assert gutenberg._best_format(formats) == ("https://gutenberg.org/2.txt", "txt")


def test_gutenberg_to_book_caches_download_url():
    item = {
        "id": 55752,
        "title": "Dom Casmurro",
        "authors": [{"name": "Machado de Assis"}],
        "languages": ["pt"],
        "formats": {
            "application/epub+zip": "https://gutenberg.org/55752.epub",
            "image/jpeg": "https://gutenberg.org/55752.jpg",
        },
    }
    book = gutenberg._to_book(item)
    assert book is not None
    assert book.id == "gutenberg-55752"
    assert book.author == "Machado de Assis"
    assert book.language == "pt"
    assert book.format == "epub"
    assert cache.get(f"{gutenberg._CACHE_NS}:{book.id}") == "https://gutenberg.org/55752.epub"


def test_gutenberg_to_book_skips_items_without_readable_format():
    item = {"id": 1, "title": "Audio only", "authors": [], "languages": [], "formats": {"audio/mpeg": "x"}}
    assert gutenberg._to_book(item) is None


def test_internet_archive_to_book_flattens_list_fields():
    doc = {
        "identifier": "domcasmurro00assi",
        "title": "Dom Casmurro",
        "creator": ["Machado de Assis"],
        "language": ["por"],
    }
    book = internet_archive._to_book(doc)
    assert book.id == "ia-domcasmurro00assi"
    assert book.author == "Machado de Assis"
    assert book.language == "por"
    assert book.cover_path.endswith("/domcasmurro00assi")


def test_direct_files_parses_size_labels():
    assert direct_files.parse_size_label("2.0 MB") == 2 * 1024 * 1024
    assert direct_files.parse_size_label("215,7 KB") == int(215.7 * 1024)
    assert direct_files.format_size(220909) == "215.7 KB"


def test_infer_ext_prefers_content_disposition_over_script_url():
    """Regression: LibGen's final download link is itself .../get.php —
    inferring the extension from that URL path used to save the file as
    "Book.php" instead of "Book.epub". The real name is in
    Content-Disposition."""
    ext = direct_files.infer_ext(
        "https://cdn3.booksdl.lc/get.php?md5=abc&key=xyz",
        "application/octet-stream",
        "pdf",
        'attachment; filename="Dom Casmurro - libgen.li.epub"',
    )
    assert ext == "epub"


def test_infer_ext_ignores_script_extension_without_content_disposition():
    ext = direct_files.infer_ext("https://cdn.example.com/get.php?id=1", "application/octet-stream", "mobi")
    assert ext == "mobi"


def test_infer_ext_still_uses_a_real_url_suffix():
    ext = direct_files.infer_ext("https://cdn.example.com/files/book.pdf", "application/pdf", "epub")
    assert ext == "pdf"


BAIXE_LISTING_HTML = """
<div class="item-inner clearfix">
  <a class="img-holder" data-src="https://www.baixelivros.com.br/media/domcasmurro.jpg"
     href="https://www.baixelivros.com.br/literatura-brasileira/dom-casmurro"></a>
  <h2 class="title">
    <a class="post-url post-title" href="https://www.baixelivros.com.br/literatura-brasileira/dom-casmurro">
      Dom Casmurro – Machado de Assis
    </a>
  </h2>
</div>
"""

BAIXE_DETAIL_HTML = """
<meta property="og:image" content="https://www.baixelivros.com.br/media/domcasmurro.jpg">
<h1 id="bltm-titulo">Dom Casmurro</h1>
<p class="bltm-autor"><span class="bltm-autor-nome">Machado de Assis</span></p>
<section class="bltm-ficha">
  <div class="bltm-detalhe-card"><dl><dt>Idioma</dt><dd>Português</dd></dl></div>
  <div class="bltm-detalhe-card"><dl><dt>Tamanho do arquivo</dt><dd>2.0 MB</dd></dl></div>
  <div class="bltm-detalhe-card"><dl><dt>Páginas</dt><dd>128</dd></dl></div>
  <div class="bltm-detalhe-card"><dl><dt>Ano</dt><dd>2019</dd></dl></div>
  <div class="bltm-detalhe-card"><dl><dt>Tipo</dt><dd>Livro Digital</dd></dl></div>
</section>
<div class="bltm-resumo"><h2>Sobre a obra</h2>Romance de Machado.</div>
<a class="bltm-acao-download" data-target="https://cdn.exemplo/dom-casmurro.pdf"
   href="/download-gratuito?dom-casmurro.pdf&pdf=https%3A%2F%2Fcdn.exemplo%2Fdom-casmurro.pdf">Baixar livro</a>
"""


def test_baixe_livros_parses_listing_cards():
    books = baixelivros.parse_listing(BAIXE_LISTING_HTML, limit=20)
    assert len(books) == 1
    book = books[0]
    assert book.title == "Dom Casmurro"
    assert book.author == "Machado de Assis"
    assert book.cover_path == "https://www.baixelivros.com.br/media/domcasmurro.jpg"
    assert book.source_id == "baixelivros"
    assert book.format == "pdf"


def test_baixe_livros_parses_details_and_direct_pdf_option():
    book = Book(
        id="https://www.baixelivros.com.br/literatura-brasileira/dom-casmurro",
        title="Dom Casmurro",
        source_id="baixelivros",
        source_name="Baixe Livros",
    )

    detailed = baixelivros.parse_details(BAIXE_DETAIL_HTML, book)

    assert detailed.author == "Machado de Assis"
    assert detailed.pages == 128
    assert detailed.year == "2019"
    assert detailed.category == "Livro Digital"
    assert detailed.synopsis == "Romance de Machado."
    assert detailed.file_options[0].format == "pdf"
    assert detailed.file_options[0].size_bytes == 2 * 1024 * 1024
    assert detailed.file_options[0].url == "https://cdn.exemplo/dom-casmurro.pdf"


BDE_LISTING_HTML = """
<div class="ep_book_grid_item_inner">
  <div class="ep_book_grid_item_thumb">
    <a href="https://bdebooks.com/pt/books/dom-casmurro-by-machado-de-assis/">
      <img src="https://bdebooks.com/pt/wp-content/uploads/dom.jpg">
    </a>
  </div>
  <div class="ep_book_grid_item_title">
    <a href="https://bdebooks.com/pt/books/dom-casmurro-by-machado-de-assis/">Dom Casmurro</a>
  </div>
  <div class="bde-card-author">Machado de Assis</div>
</div>
"""

BDE_DETAIL_HTML = """
<meta property="og:image" content="https://bdebooks.com/pt/wp-content/uploads/dom.jpg">
<h1 class="ep_single_book_top_title">Dom Casmurro</h1>
<div class="ep_single_book_top_author"><a>Machado de Assis</a></div>
<div class="bde-quickfacts">
  <span class="bde-qf">PDF / EPUB</span>
  <span class="bde-qf">212 páginas</span>
  <span class="bde-qf">1.12 MB</span>
</div>
<ul class="ep_single_book_top_meta">
  <li>Primeira publicação: <b>1899</b></li>
  <li>Gênero: <a>Clássicos</a></li>
</ul>
<div class="ep_single_book_top_content"><p>Bento Santiago conta a própria história.</p></div>
<div class="ep_pdf_book_link_handler"
  data-pdf-book-link="https://bdebooks.com/ptdl/dom.pdf"
  data-epub-book-link="https://bdebooks.com/ptdl/dom.epub"
  data-mobi-book-link=""></div>
"""


def test_bdebooks_parses_listing_cards():
    books = bdebooks.parse_listing(BDE_LISTING_HTML, limit=20)
    assert len(books) == 1
    book = books[0]
    assert book.title == "Dom Casmurro"
    assert book.author == "Machado de Assis"
    assert book.cover_path == "https://bdebooks.com/pt/wp-content/uploads/dom.jpg"
    assert book.source_id == "bdebooks"


def test_bdebooks_parses_details_and_format_options():
    book = Book(
        id="https://bdebooks.com/pt/books/dom-casmurro-by-machado-de-assis/",
        title="Dom Casmurro",
        source_id="bdebooks",
        source_name="BDeBooks",
    )

    detailed = bdebooks.parse_details(BDE_DETAIL_HTML, book)

    assert detailed.author == "Machado de Assis"
    assert detailed.pages == 212
    assert detailed.year == "1899"
    assert detailed.category == "Clássicos"
    assert detailed.synopsis == "Bento Santiago conta a própria história."
    assert [option.format for option in detailed.file_options] == ["pdf", "epub"]
    assert detailed.file_options[0].url == "https://bdebooks.com/ptdl/dom.pdf"


ZONA_FANTASMA_LISTING_HTML = """
<div class="page-content">
  <article class="post">
    <h2 class="entry-title"><a href="https://zonafantasmanet.com.br/superman-1/">Superman #1</a></h2>
    <a href="https://zonafantasmanet.com.br/superman-1/"><img src="https://zonafantasmanet.com.br/wp-content/superman-1.jpg"></a>
  </article>
  <article class="post">
    <h2 class="entry-title"><a href="https://zonafantasmanet.com.br/superman-2/">Superman #2</a></h2>
    <a href="https://zonafantasmanet.com.br/superman-2/"><img src="https://zonafantasmanet.com.br/wp-content/superman-2.jpg"></a>
  </article>
</div>
"""

ZONA_FANTASMA_POST_HTML = """
<div class="elementor-widget-image">
  <a href="https://www.mediafire.com/file/abc123/Superman.cbr/file" target="_blank">
    <img src="https://zonafantasmanet.com.br/wp-content/cover.jpg">
  </a>
</div>
<a href="https://t.me/zonafantasmaoficial">Telegram</a>
"""

MEDIAFIRE_PAGE_HTML = """
<a class="input popsok" href="https://download123.mediafire.com/xyz/abc123/Superman.cbr" id="downloadButton" rel="nofollow">
  Download (10MB)
</a>
"""


def test_zona_fantasma_parses_post_listing():
    books = zona_fantasma._parse_listing(ZONA_FANTASMA_LISTING_HTML, limit=20)
    assert len(books) == 2
    assert books[0].title == "Superman #1"
    assert books[0].id == "https://zonafantasmanet.com.br/superman-1/"
    assert books[0].cover_path == "https://zonafantasmanet.com.br/wp-content/superman-1.jpg"
    assert books[0].source_id == "zonafantasma"
    assert books[0].format == "cbr"


def test_zona_fantasma_parses_post_listing_respects_limit():
    books = zona_fantasma._parse_listing(ZONA_FANTASMA_LISTING_HTML, limit=1)
    assert len(books) == 1


def test_zona_fantasma_finds_mediafire_link_and_ignores_social_links():
    link = zona_fantasma._find_mediafire_link(ZONA_FANTASMA_POST_HTML)
    assert link == "https://www.mediafire.com/file/abc123/Superman.cbr/file"


def test_zona_fantasma_returns_none_when_no_mediafire_link():
    assert zona_fantasma._find_mediafire_link("<a href='https://t.me/x'>x</a>") is None


MULTIVERSO_HQ_LISTING_HTML = """
<ul class="videos">
  <li>
    <div class="video-conteudo">
      <div class="thumb-conteudo">
        <a href="https://multiversohq.com/batman-1/" title="Batman #1">
          <img class="thumb" src="https://multiversohq.com/wp-content/batman-1.jpg">
        </a>
      </div>
      <a class="titulo" href="https://multiversohq.com/batman-1/" title="Batman #1">
        <h2>Batman #1</h2>
      </a>
    </div>
  </li>
</ul>
"""


def test_multiverso_hq_parses_video_style_listing():
    books = multiverso_hq._parse_listing(MULTIVERSO_HQ_LISTING_HTML, limit=20)
    assert len(books) == 1
    book = books[0]
    assert book.title == "Batman #1"
    assert book.id == "https://multiversohq.com/batman-1/"
    assert book.cover_path == "https://multiversohq.com/wp-content/batman-1.jpg"
    assert book.source_id == "multiversohq"


def test_multiverso_hq_finds_external_download_link_and_ignores_own_domain():
    html = """
    <a href="https://multiversohq.com/batman-1/">Voltar</a>
    <a href="https://workupload.com/file/xyz">Baixar</a>
    """
    assert multiverso_hq._find_download_link(html) == "https://workupload.com/file/xyz"


def test_multiverso_hq_returns_none_when_no_external_link():
    assert multiverso_hq._find_download_link("<a href='https://multiversohq.com/x'>x</a>") is None


def test_multiverso_hq_download_requires_manual_browser(monkeypatch, tmp_path):
    class Response:
        text = '<a href="https://workupload.com/file/xyz">Baixar</a>'

        def raise_for_status(self):
            return None

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def get(self, url):
            return Response()

    monkeypatch.setattr(multiverso_hq, "new_client", lambda timeout=20: Client())
    book = Book(
        id="https://multiversohq.com/batman-1/",
        title="Batman #1",
        source_id="multiversohq",
        source_name="Multiverso HQ",
        format="cbr",
    )

    with pytest.raises(ManualDownloadRequired) as exc:
        multiverso_hq.download(book, tmp_path)

    assert exc.value.url == "https://workupload.com/file/xyz"
    assert "navegador real" in str(exc.value)


LIBGEN_RESULTS_HTML = """
<table id="tablelibgen">
<thead><tr><th>ID</th><th>Title</th><th>Author(s)</th><th>Publisher</th><th>Year</th><th>Language</th><th>Pages</th><th>Size</th><th>Ext.</th><th>Mirrors</th></tr></thead>
<tbody>
<tr>
<td><b>Dom Casmurro 2</b><br><a href="edition.php?id=5804811">Dom Casmurro <i></i></a></td>
<td>Assis, Machado De</td>
<td></td>
<td></td>
<td>Portuguese</td>
<td>0</td>
<td><nobr><a href="/file.php?id=6055539">202 kB</a></nobr></td>
<td>epub</td>
<td><a href="/ads.php?md5=54dd396ae2cd6eed152e6e6ded2ba988">1</a></td>
</tr>
<tr>
<td><a href="edition.php?id=999">Dom Casmurro <i></i></a></td>
<td>De Assis, Machado</td>
<td></td>
<td></td>
<td>English</td>
<td>0</td>
<td><nobr><a href="/file.php?id=111">1.1 MB</a></nobr></td>
<td>txt</td>
<td><a href="/ads.php?md5=abc">1</a></td>
</tr>
</tbody>
</table>
"""


def test_libgen_parses_results_with_per_item_language():
    """LibGen mixes languages in one search — every row has to carry its
    own language, since that's the only way to tell a Portuguese edition
    from an English one before opening it."""
    books = libgen.parse_results(LIBGEN_RESULTS_HTML, limit=20)
    assert len(books) == 2
    assert books[0].title == "Dom Casmurro"
    assert books[0].language == "Portuguese"
    assert books[0].format == "epub"
    assert books[0].id == "https://libgen.li/file.php?id=6055539"
    assert books[0].file_size_bytes == direct_files.parse_size_label("202 kB")
    assert books[1].language == "English"
    assert books[1].format == "txt"


def test_libgen_parse_results_respects_limit():
    books = libgen.parse_results(LIBGEN_RESULTS_HTML, limit=1)
    assert len(books) == 1


def test_libgen_parse_results_empty_when_no_table():
    assert libgen.parse_results("<p>sem resultados</p>", limit=20) == []


def test_libgen_cover_from_handles_multiple_collection_prefixes():
    """Regression: a downloaded LibGen book had no cover because the
    selector only matched "/covers/" — this book's page used
    "/fictioncovers/" instead (a different LibGen sub-collection)."""
    from bs4 import BeautifulSoup

    fiction_html = '<img src="/fictioncovers/2760000/abc.jpg" width=200>'
    plain_html = '<img src="/covers/2043000/def.jpg" width=200>'
    assert libgen._cover_from(BeautifulSoup(fiction_html, "html.parser")) == "https://libgen.li/fictioncovers/2760000/abc.jpg"
    assert libgen._cover_from(BeautifulSoup(plain_html, "html.parser")) == "https://libgen.li/covers/2043000/def.jpg"
    assert libgen._cover_from(BeautifulSoup("<img src='/img/logo.png'>", "html.parser")) is None


LIBGEN_FILE_PAGE_HTML = """
<div><a href="/ads.php?md5=54dd396ae2cd6eed152e6e6ded2ba988">Libgen</a></div>
"""

LIBGEN_ADS_PAGE_HTML = """
<a href="get.php?md5=54dd396ae2cd6eed152e6e6ded2ba988&key=3OFP479XSAP5S9KI"><h2>GET</h2></a>
"""


def test_libgen_resolve_direct_url(monkeypatch):
    class _Resp:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    class _Client:
        def get(self, url, headers=None):
            if "file.php" in url:
                assert headers is None
                return _Resp(LIBGEN_FILE_PAGE_HTML)
            if "ads.php" in url:
                assert headers == {"Referer": "https://libgen.li/file.php?id=6055539"}
                return _Resp(LIBGEN_ADS_PAGE_HTML)
            raise AssertionError(f"unexpected url {url}")

    direct_url, referer = libgen._resolve_direct_url(_Client(), "https://libgen.li/file.php?id=6055539")
    assert direct_url == "https://libgen.li/get.php?md5=54dd396ae2cd6eed152e6e6ded2ba988&key=3OFP479XSAP5S9KI"
    assert referer == "https://libgen.li/ads.php?md5=54dd396ae2cd6eed152e6e6ded2ba988"
