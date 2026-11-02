"""
Command line interface for py-wiki-crawler.
Provides rich terminal feedback, progress tracking, and configuration options.
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from py_wiki_crawler import __version__
from py_wiki_crawler.core.engine import CrawlEngine, EngineConfig

console = Console()


def setup_logging(verbose: bool) -> None:
    """Configures logging level and format."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    )


def build_parser() -> argparse.ArgumentParser:
    """Builds the argument parser for CLI execution."""
    parser = argparse.ArgumentParser(
        prog="py-wiki-crawler",
        description=(
            "Lädt Wiki-Seiten (Fandom, MediaWiki oder HTML) rekursiv herunter und speichert sie "
            "als verlinktes Markdown-Archiv mit Grafiken."
        ),
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="Start-URL des Wikis (z.B. https://genshin-impact.fandom.com)",
    )
    parser.add_argument("-u", "--url", dest="opt_url", help="Alternative Angabe der Start-URL")
    parser.add_argument(
        "-o",
        "--output",
        default="wiki_export",
        help="Zielordner für die Markdown-Dateien und Grafiken (Standard: wiki_export)",
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=0.4,
        help="Verzögerung zwischen HTTP-Anfragen in Sekunden (Standard: 0.4s)",
    )
    parser.add_argument(
        "-m",
        "--max-pages",
        type=int,
        default=None,
        help="Maximale Seitenanzahl zum Herunterladen (hilfreich für Tests)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=5,
        help="Maximale Klicktiefe für den HTML-Crawler (Standard: 5)",
    )
    parser.add_argument(
        "--no-images", action="store_true", help="Deaktiviert den Download von Bildern und Grafiken"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Lädt alle Seiten neu. Ohne diese Option überspringt ein erneuter Lauf "
            "fertige Seiten und versucht nur fehlgeschlagene/neue Seiten"
        ),
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Startet die grafische Benutzeroberfläche (PySide6 GUI)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Aktiviert ausführliches Debug-Logging"
    )
    parser.add_argument("--version", action="version", version=f"py-wiki-crawler {__version__}")

    return parser


def main() -> None:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    if args.gui:
        from py_wiki_crawler.gui.app import run_gui

        sys.exit(run_gui())

    if args.gui:
        from py_wiki_crawler.gui.app import run_gui
        sys.exit(run_gui())

    wiki_url = args.url or args.opt_url
    if not wiki_url:
        # If launched with no args from interactive console, offer or start GUI
        console.print("[bold red]Fehler:[/] Bitte gib eine Wiki-URL an oder nutze [cyan]--gui[/]!")
        parser.print_help()
        sys.exit(1)

    setup_logging(args.verbose)

    output_path = Path(args.output).resolve()

    img_status = (
        "Deaktiviert" if args.no_images else "Aktiv (Originalauflösung + SHA-256 Deduplizierung)"
    )
    mode_status = (
        "Alles neu laden" if args.force else "Fortsetzen (fertige Seiten werden übersprungen)"
    )

    # Header Panel
    console.print(
        Panel.fit(
            f"[bold cyan]py-wiki-crawler v{__version__}[/]\n"
            f"[bold]Wiki-URL:[/] [underline]{wiki_url}[/]\n"
            f"[bold]Zielordner:[/] {output_path}\n"
            f"[bold]Modus:[/] {mode_status}\n"
            f"[bold]Bilder:[/] {img_status}",
            title="[bold green]Wiki Export Manager[/]",
            border_style="cyan",
        )
    )

    config = EngineConfig(
        base_url=wiki_url,
        output_dir=output_path,
        delay=args.delay,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        save_images=not args.no_images,
        force_refresh=args.force,
    )

    engine = CrawlEngine(config)

    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_pages = progress.add_task("[cyan]Verarbeite Artikel...", total=args.max_pages or 100)

        def on_discovered(url: str, title: str) -> None:
            if not args.max_pages:
                progress.update(
                    task_pages,
                    total=max(
                        progress.tasks[0].total or 0,
                        len(engine.state_manager.get_pending_pages()) + 1,
                    ),
                )

        def on_processed(url: str, title: str, local_path: Path) -> None:
            progress.advance(task_pages)
            stats = engine.state_manager.get_stats()
            short_title = title[:20] + "..." if len(title) > 20 else title
            task_desc = f"[cyan]Artikel: [bold]{short_title}[/] (Bilder: {stats['total_images']})"
            progress.update(task_pages, description=task_desc)

        def on_failed(url: str, title: str, error: str) -> None:
            progress.advance(task_pages)

        engine.on_page_discovered = on_discovered
        engine.on_page_processed = on_processed
        engine.on_page_failed = on_failed

        stats = engine.run()

    duration = time.time() - start_time

    # Summary Table
    summary_table = Table(title="[bold green]Export-Zusammenfassung[/]", border_style="green")
    summary_table.add_column("Metrik", style="bold white")
    summary_table.add_column("Wert", style="bold cyan")

    summary_table.add_row("Dauer", f"{duration:.2f} Sekunden")
    summary_table.add_row("Erfolgreich exportierte Seiten", str(stats.get("done_pages", 0)))
    summary_table.add_row("Fehlgeschlagene Seiten", str(stats.get("failed_pages", 0)))
    summary_table.add_row("Heruntergeladene Grafiken", str(stats.get("total_images", 0)))
    summary_table.add_row("Zielordner", str(output_path))

    console.print("\n", summary_table)
    console.print(
        f"[bold green]✔ Export erfolgreich abgeschlossen![/] "
        f"Dateien liegen in: [underline]{output_path}[/]\n"
    )


if __name__ == "__main__":
    main()
