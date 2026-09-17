"""Sapphire Box CLI — the whole Phase 0 surface (no GUI yet, by design).

`sapphirebox manga search -s mangalivre "one piece"`
`sapphirebox manga download <manga_url> -s niadd -c 1-3`
`sapphirebox books search "dom casmurro"`
`sapphirebox library list`
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

import typer
from rich.console import Console
from rich.table import Table

from sapphirebox.books import manager as books_manager
from sapphirebox.books.sources.base import ManualDownloadRequired
from sapphirebox.books.sources import registry as books_registry
from sapphirebox.core import config
from sapphirebox.core.models import Book
from sapphirebox.library import service as library_service
from sapphirebox.manga import manager as manga_manager
from sapphirebox.manga.sources import registry as manga_registry

console = Console()

app = typer.Typer(help="Sapphire Box — mangas, manhwas e livros, organizados e de graça.", no_args_is_help=True)
manga_app = typer.Typer(help="Buscar, listar e baixar mangas/manhwas.", no_args_is_help=True)
books_app = typer.Typer(help="Buscar e baixar livros (epub/pdf/txt).", no_args_is_help=True)
library_app = typer.Typer(help="Biblioteca local (o que ja foi baixado).", no_args_is_help=True)
app.add_typer(manga_app, name="manga")
app.add_typer(books_app, name="books")
app.add_typer(library_app, name="library")


def _normal_host(raw_url: str) -> str:
    parsed = urlparse(raw_url if "://" in raw_url else f"https://{raw_url}")
    host = parsed.netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _host_matches(raw_url: str, source_url: str) -> bool:
    url_host = _normal_host(raw_url)
    source_host = _normal_host(source_url)
    return bool(url_host and source_host and (url_host == source_host or url_host.endswith(f".{source_host}")))


def _implemented_manga_sources():
    return [s for s in manga_registry.load_source_infos() if s.has_python_source]


def _implemented_book_sources():
    return [s for s in books_registry.load_source_infos() if s.has_python_source]


def _detect_source(raw_url: str) -> tuple[str, str, str] | None:
    for source in _implemented_manga_sources():
        if _host_matches(raw_url, source.url):
            return ("manga", source.id, source.name)
    for source in _implemented_book_sources():
        if _host_matches(raw_url, source.url):
            return ("book", source.id, source.name)
    return None


def _source_name(kind: str, source_id: str) -> str:
    sources = _implemented_manga_sources() if kind == "manga" else _implemented_book_sources()
    for source in sources:
        if source.id == source_id:
            return source.name
    return source_id


def _kind_for_source(source_id: str) -> str | None:
    if any(s.id == source_id for s in _implemented_manga_sources()):
        return "manga"
    if any(s.id == source_id for s in _implemented_book_sources()):
        return "book"
    return None


def _normalize_kind(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    if normalized in {"manga", "mangá", "manhwa", "manhua"}:
        return "manga"
    if normalized in {"book", "books", "livro", "livros", "hq", "quadrinho", "quadrinhos"}:
        return "book"
    return None


def _prompt_choice(label: str, choices: list[str], default: str | None = None) -> str:
    while True:
        value = typer.prompt(label, default=default or choices[0]).strip()
        if value in choices:
            return value
        console.print(f"[yellow]Escolha uma destas opções:[/yellow] {', '.join(choices)}")


def _prompt_kind(default: str | None = None) -> str:
    while True:
        raw = typer.prompt("Tipo (manga/livro)", default=default or "manga")
        kind = _normalize_kind(raw)
        if kind:
            return kind
        console.print("[yellow]Use manga ou livro.[/yellow]")


def _prompt_source(kind: str) -> str:
    sources = _implemented_manga_sources() if kind == "manga" else _implemented_book_sources()
    choices = [s.id for s in sources]
    table = Table("id", "nome", "url", title="Fontes disponíveis")
    for source in sources:
        table.add_row(source.id, source.name, source.url)
    console.print(table)
    return _prompt_choice("Fonte", choices)


def _prompt_output_dir(kind: str, output: Path | None) -> Path:
    if output is None:
        default = config.get_library_path() if kind == "manga" else config.get_books_library_path()
        output = Path(typer.prompt("Pasta para salvar", default=str(default)))
    output = output.expanduser()
    output.mkdir(parents=True, exist_ok=True)
    return output


def _guess_title_from_url(raw_url: str, fallback: str) -> str:
    parsed = urlparse(raw_url)
    last = Path(unquote(parsed.path.rstrip("/"))).name
    cleaned = " ".join(last.replace("-", " ").replace("_", " ").split())
    return cleaned or fallback


def _book_id_from_url(source_id: str, raw_url: str) -> str:
    parsed = urlparse(raw_url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if source_id == "gutenberg":
        for part in reversed(path_parts):
            if part.isdigit():
                return f"gutenberg-{part}"
    if source_id == "internet_archive":
        for marker in ("details", "download"):
            if marker in path_parts:
                idx = path_parts.index(marker)
                if idx + 1 < len(path_parts):
                    return f"ia-{path_parts[idx + 1]}"
    return raw_url


def _download_manga_from_cli(source_id: str, raw_url: str, output: Path, chapters: str | None, fmt: str | None) -> None:
    chapters = chapters if chapters is not None else typer.prompt("Capítulos", default="all")
    fmt = fmt or "cbz"
    title = None
    try:
        details = manga_manager.get_details(source_id, raw_url)
        title = details.title if details else None
    except Exception:
        title = None

    def on_progress(pct: int, msg: str) -> None:
        console.print(f"[cyan]{pct:3d}%[/cyan] {msg}")

    try:
        manga = manga_manager.download(
            source_id,
            raw_url,
            chapters,
            fmt,
            dest_root=output,
            on_progress=on_progress,
            title=title,
        )
    except RuntimeError as exc:
        console.print(f"[red]Falhou:[/red] {exc}")
        raise typer.Exit(code=1)
    console.print(f"[green]Concluido:[/green] {manga.title} -> {manga.local_path}")


def _download_book_from_cli(
    source_id: str,
    source_name: str,
    raw_url: str,
    output: Path,
    fmt: str | None,
    title: str | None,
) -> None:
    book_id = _book_id_from_url(source_id, raw_url)
    default_format = fmt or ("epub" if source_id in {"gutenberg", "internet_archive"} else "")
    book = Book(
        id=book_id,
        title=title or _guess_title_from_url(raw_url, book_id),
        source_id=source_id,
        source_name=source_name,
        format=default_format,
    )

    def on_progress(pct: int, msg: str) -> None:
        console.print(f"[cyan]{pct:3d}%[/cyan] {msg}")

    try:
        detailed = books_manager.get_details(book)
        if title:
            detailed.title = title
        book = books_manager.download(detailed, output, on_progress=on_progress)
    except ManualDownloadRequired as exc:
        console.print(f"[yellow]Download manual necessário:[/yellow] {exc}")
        console.print(f"Abra: [cyan]{exc.url}[/cyan]")
        raise typer.Exit(code=2)
    except RuntimeError as exc:
        console.print(f"[red]Falhou:[/red] {exc}")
        raise typer.Exit(code=1)
    console.print(f"[green]Concluido:[/green] {book.title} -> {book.local_path}")


def _guided_download(
    raw_url: str | None,
    kind: str | None,
    source: str | None,
    output: Path | None,
    chapters: str | None,
    fmt: str | None,
    title: str | None,
) -> None:
    raw_url = (raw_url or typer.prompt("Site/URL para extrair")).strip()
    if not raw_url:
        console.print("[red]Informe uma URL.[/red]")
        raise typer.Exit(code=1)

    normalized_kind = _normalize_kind(kind)
    detected = _detect_source(raw_url)
    if source is None and detected:
        detected_kind, source, name = detected
        normalized_kind = normalized_kind or detected_kind
        console.print(f"Fonte detectada: [bold]{name}[/bold] ({source})")

    if source and normalized_kind is None:
        normalized_kind = _kind_for_source(source)
    if normalized_kind is None:
        normalized_kind = _prompt_kind()
    if source is None:
        source = _prompt_source(normalized_kind)
    source_name = _source_name(normalized_kind, source)

    output_dir = _prompt_output_dir(normalized_kind, output)
    if normalized_kind == "manga":
        _download_manga_from_cli(source, raw_url, output_dir, chapters, fmt)
    else:
        _download_book_from_cli(source, source_name, raw_url, output_dir, fmt, title)


@app.command("baixar")
def guided_download_pt(
    url: str | None = typer.Argument(None, help="URL do manga/livro. Se vazio, o terminal pergunta."),
    kind: str | None = typer.Option(None, "--kind", "-k", help="manga ou livro; detectado pela URL quando possível."),
    source: str | None = typer.Option(None, "--source", "-s", help="Força a fonte, ex: mangalivre, niadd, baixelivros."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Pasta onde salvar o arquivo."),
    chapters: str | None = typer.Option(None, "--chapters", "-c", help="Para mangas: all, 1-5, 1,3,7."),
    fmt: str | None = typer.Option(None, "--format", "-f", help="Formato desejado quando a fonte oferecer opções."),
    title: str | None = typer.Option(None, "--title", help="Nome usado para salvar livros quando a fonte não informa título."),
):
    """Fluxo guiado: pergunta URL, fonte/pasta quando precisar, e baixa."""
    _guided_download(url, kind, source, output, chapters, fmt, title)


@app.command("wizard")
def guided_download_en(
    url: str | None = typer.Argument(None, help="URL do manga/livro. Se vazio, o terminal pergunta."),
    kind: str | None = typer.Option(None, "--kind", "-k", help="manga ou livro; detectado pela URL quando possível."),
    source: str | None = typer.Option(None, "--source", "-s", help="Força a fonte, ex: mangalivre, niadd, baixelivros."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Pasta onde salvar o arquivo."),
    chapters: str | None = typer.Option(None, "--chapters", "-c", help="Para mangas: all, 1-5, 1,3,7."),
    fmt: str | None = typer.Option(None, "--format", "-f", help="Formato desejado quando a fonte oferecer opções."),
    title: str | None = typer.Option(None, "--title", help="Nome usado para salvar livros quando a fonte não informa título."),
):
    """Alias de `baixar`, inspirado em CLIs interativas tipo Benny-Scraper."""
    _guided_download(url, kind, source, output, chapters, fmt, title)


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port", "-p"),
    reload: bool = typer.Option(False, "--reload", help="Recarrega ao editar arquivos (dev)"),
):
    """Sobe o preview web local (backend + frontend) em http://host:port."""
    import uvicorn

    console.print(f"[bold]Sapphire Box web[/bold] em [cyan]http://{host}:{port}[/cyan] (Ctrl+C pra parar)")
    uvicorn.run("sapphirebox.web.server:app", host=host, port=port, reload=reload)


@app.command()
def desktop():
    """Abre o Sapphire Box numa janela nativa (macOS/Linux/Windows), via pywebview."""
    from sapphirebox.desktop.app import main as run_desktop

    try:
        run_desktop()
    except RuntimeError as exc:
        console.print(f"[red]Falhou:[/red] {exc}")
        raise typer.Exit(code=1)


@app.command()
def init():
    """Cria os diretorios de dados/biblioteca e o banco SQLite."""
    from sapphirebox.core import db

    config.initialize_app_paths()
    db.get_connection()
    console.print(f"[bold]Biblioteca de mangas:[/bold] {config.get_library_path()}")
    console.print(f"[bold]Biblioteca de livros:[/bold] {config.get_books_library_path()}")
    console.print(f"[bold]Banco de dados:[/bold] {config.get_database_path()}")


# --- manga -------------------------------------------------------------

@manga_app.command("sources")
def manga_sources():
    """Lista as fontes de manga configuradas."""
    table = Table("id", "nome", "idioma", "prioridade", "status")
    for s in manga_registry.load_source_infos():
        status = "implementado" if s.has_python_source else "nao implementado"
        style = "" if s.enabled else "dim"
        table.add_row(s.id, s.name, s.language, str(s.priority), status, style=style)
    console.print(table)


@manga_app.command("search")
def manga_search(
    query: str,
    source: str = typer.Option(..., "--source", "-s", help="mangalivre | niadd"),
    page: int = typer.Option(1, "--page", "-p"),
):
    """Busca ao vivo numa fonte especifica."""
    results, total_pages = manga_manager.search_web(source, query, page)
    if not results:
        console.print("[yellow]Nenhum resultado.[/yellow]")
        raise typer.Exit()

    table = Table("titulo", "capitulos", "id/url", title=f"pagina {page}/{total_pages}")
    for m in results:
        table.add_row(m.title, str(m.total_chapters or "-"), m.id)
    console.print(table)


@manga_app.command("download")
def manga_download(
    manga_id: str = typer.Argument(..., help="URL/id do manga (retornado pelo search)"),
    source: str = typer.Option(..., "--source", "-s"),
    chapters: str = typer.Option("all", "--chapters", "-c", help="ex: all, 1-5, 1,3,7"),
    fmt: str = typer.Option("cbz", "--format", "-f"),
):
    """Baixa capitulos usando o downloader implementado da fonte."""
    def on_progress(pct: int, msg: str) -> None:
        console.print(f"[cyan]{pct:3d}%[/cyan] {msg}")

    try:
        manga = manga_manager.download(source, manga_id, chapters, fmt, on_progress=on_progress)
    except RuntimeError as exc:
        console.print(f"[red]Falhou:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(
        f"[green]Concluido:[/green] {manga.title} -> {manga.local_path} "
        f"({manga.downloaded_chapters} capitulos)"
    )


# --- books ---------------------------------------------------------------

@books_app.command("sources")
def books_sources():
    """Lista as fontes de livros implementadas + o catálogo pesquisado (ainda não ligado)."""
    table = Table("id", "nome", "formatos", "status", title="Implementadas")
    for s in books_registry.list_enabled():
        table.add_row(s.id, s.name, ", ".join(s.formats), "implementado")
    console.print(table)

    catalog = books_registry.load_document_catalog()
    if catalog:
        cat_table = Table("id", "nome", "categoria", "formatos", "busca", title="Catálogo (Fase 2 — motor genérico)")
        for s in catalog:
            cat_table.add_row(s.id, s.name, s.category, ", ".join(s.formats), s.renderer)
        console.print(cat_table)


@books_app.command("search")
def books_search(
    query: str,
    source: str = typer.Option(None, "--source", "-s", help="gutenberg | internet_archive (default: todas)"),
    limit: int = typer.Option(20, "--limit", "-n"),
):
    """Busca livros por titulo/autor."""
    results, _ = books_manager.search(query, source, limit)
    if not results:
        console.print("[yellow]Nenhum resultado.[/yellow]")
        raise typer.Exit()

    table = Table("titulo", "autor", "fonte", "formato", "id")
    for b in results:
        table.add_row(b.title, b.author or "-", b.source_name, b.format, b.id)
    console.print(table)


@books_app.command("download")
def books_download(
    book_id: str = typer.Argument(..., help="id retornado pelo search (ex: gutenberg-1342)"),
    source: str = typer.Option(..., "--source", "-s"),
    title: str = typer.Option(None, "--title", help="opcional, so para nomear o arquivo"),
):
    """Baixa um livro pelo id retornado por `books search`."""
    stub = Book(id=book_id, title=title or book_id, source_id=source, source_name=source)
    try:
        book = books_manager.download(stub)
    except RuntimeError as exc:
        console.print(f"[red]Falhou:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(f"[green]Concluido:[/green] {book.title} -> {book.local_path}")


# --- library ---------------------------------------------------------------

@library_app.command("sync")
def library_sync():
    """Reindexa a pasta da biblioteca de mangas no banco local."""
    scanned = library_service.sync_local_library(config.get_library_path())
    console.print(f"{len(scanned)} manga(s) sincronizados de {config.get_library_path()}")


@library_app.command("list")
def library_list(page: int = typer.Option(1, "--page", "-p")):
    """Lista o que ja esta na biblioteca local (banco de dados)."""
    items, total_pages = library_service.list_library(page=page)
    if not items:
        console.print("[yellow]Biblioteca vazia. Rode `sapphirebox library sync` apos baixar algo.[/yellow]")
        raise typer.Exit()

    table = Table("titulo", "fonte", "capitulos", "caminho", title=f"pagina {page}/{total_pages}")
    for m in items:
        table.add_row(m.title, m.source_name, str(m.downloaded_chapters), m.local_path)
    console.print(table)


@library_app.command("books")
def library_books(page: int = typer.Option(1, "--page", "-p")):
    """Lista os livros ja baixados."""
    items, total_pages = books_manager.list_library(page=page)
    if not items:
        console.print("[yellow]Nenhum livro baixado ainda.[/yellow]")
        raise typer.Exit()

    table = Table("titulo", "autor", "fonte", "caminho", title=f"pagina {page}/{total_pages}")
    for b in items:
        table.add_row(b.title, b.author or "-", b.source_name, b.local_path or "-")
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
