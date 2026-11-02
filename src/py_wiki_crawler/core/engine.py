"""
Core crawl and conversion engine.
Coordinates extraction, markdown conversion, image downloading, and SQLite state tracking.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests

from py_wiki_crawler.converters.images import ImageDownloader
from py_wiki_crawler.converters.markdown import MarkdownConverter
from py_wiki_crawler.core.rate_limiter import RateLimiter
from py_wiki_crawler.core.state import StateManager
from py_wiki_crawler.extractors.base import BaseExtractor
from py_wiki_crawler.extractors.html_crawler import HtmlCrawlerExtractor
from py_wiki_crawler.extractors.mediawiki import MediaWikiExtractor
from py_wiki_crawler.utils.path_utils import title_to_relative_path

logger = logging.getLogger("py_wiki_crawler.engine")


@dataclass
class EngineConfig:
    """Configuration options for the CrawlEngine."""

    base_url: str
    output_dir: Path
    delay: float = 0.4
    max_pages: int | None = None
    max_depth: int = 5
    save_images: bool = True
    resume: bool = False
    image_workers: int = 4
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 (WikiMarkdownExporter/2.0)"
    )


class CrawlEngine:
    """The central orchestrator for crawling, downloading, and converting wikis."""

    def __init__(self, config: EngineConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.output_dir / ".crawler_state.db"
        self.state_manager = StateManager(self.db_path)

        self.rate_limiter = RateLimiter(base_delay=config.delay)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})

        self.image_downloader: ImageDownloader | None = None
        if config.save_images:
            self.image_downloader = ImageDownloader(
                output_dir=self.output_dir,
                state_manager=self.state_manager,
                rate_limiter=self.rate_limiter,
                session=self.session,
            )

        self.markdown_converter = MarkdownConverter(
            base_url=config.base_url, output_dir=self.output_dir
        )

        self.extractor: BaseExtractor = self._init_extractor()
        self._stop_requested = False

        # Callbacks for CLI / UI progress tracking
        self.on_page_discovered: Callable[[str, str], None] | None = None
        self.on_page_processed: Callable[[str, str, Path], None] | None = None
        self.on_page_failed: Callable[[str, str, str], None] | None = None
        self.on_log: Callable[[str, str], None] | None = None

    def stop(self) -> None:
        """Requests cancellation of the ongoing crawl."""
        self._stop_requested = True
        logger.info("Abbruch angefordert...")

    def _init_extractor(self) -> BaseExtractor:
        """Probes for MediaWiki API; falls back to BFS HTML crawler if not detected."""
        api_endpoint = MediaWikiExtractor.detect_api(self.config.base_url, self.session)
        if api_endpoint:
            logger.info(f"MediaWiki API aktiv: {api_endpoint}")
            self.state_manager.set_metadata("extractor_type", "mediawiki")
            self.state_manager.set_metadata("api_endpoint", api_endpoint)
            return MediaWikiExtractor(
                base_url=self.config.base_url,
                api_endpoint=api_endpoint,
                session=self.session,
                rate_limiter=self.rate_limiter,
            )
        else:
            logger.info("Keine MediaWiki API gefunden. Starte rekursiven HTML-Crawler.")
            self.state_manager.set_metadata("extractor_type", "html_crawler")
            return HtmlCrawlerExtractor(
                base_url=self.config.base_url,
                session=self.session,
                rate_limiter=self.rate_limiter,
                max_depth=self.config.max_depth,
            )

    def run(self) -> dict[str, int]:
        """Runs the crawl and conversion process."""
        logger.info(f"Starte Crawl für: {self.config.base_url}")
        logger.info(f"Zielverzeichnis: {self.output_dir.resolve()}")

        # 1. Discover or populate initial queue if not resuming or queue empty
        pending = self.state_manager.get_pending_pages()
        if not self.config.resume or not pending:
            discovered_pages: list[tuple[str, str, int]] = []
            for item in self.extractor.discover_pages(max_pages=self.config.max_pages):
                if self._stop_requested:
                    logger.info("Entdeckungsvorgang durch Benutzer abgebrochen.")
                    break
                discovered_pages.append(item)
                if self.on_page_discovered:
                    self.on_page_discovered(item[0], item[1])

            self.state_manager.add_pages_bulk(discovered_pages)

        # 2. Main processing loop
        processed_count = 0
        while not self._stop_requested:
            pending_batch = self.state_manager.get_pending_pages(limit=50)
            if not pending_batch:
                break

            for item in pending_batch:
                if self._stop_requested:
                    logger.info("Crawl durch Benutzer abgebrochen.")
                    return self.state_manager.get_stats()

                if self.config.max_pages and processed_count >= self.config.max_pages:
                    logger.info(f"Maximale Seitenanzahl ({self.config.max_pages}) erreicht.")
                    return self.state_manager.get_stats()

                url = item["url"]
                title = item["title"]
                depth = item["depth"]

                try:
                    self._process_single_page(url, title, depth)
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Fehler bei Seite '{title}' ({url}): {e}")
                    self.state_manager.mark_page_failed(url, str(e))
                    if self.on_page_failed:
                        self.on_page_failed(url, title, str(e))

        stats = self.state_manager.get_stats()
        logger.info(
            f"Crawl abgeschlossen: {stats['done_pages']} Seiten exportiert, "
            f"{stats['failed_pages']} fehlgeschlagen, {stats['total_images']} Bilder gesichert."
        )
        return stats

    def _process_single_page(self, url: str, fallback_title: str, depth: int) -> None:
        """Fetches, converts, and writes a single wiki article."""
        result = self.extractor.fetch_page_content(url)
        if not result:
            self.state_manager.mark_page_failed(url, "Kein Inhalt empfangen", http_status=404)
            if self.on_page_failed:
                self.on_page_failed(url, fallback_title, "Kein Inhalt")
            return

        actual_title, html_content, source_url = result
        final_title = actual_title or fallback_title

        # Determine target file path
        rel_file_path = title_to_relative_path(final_title)
        full_dest_path = self.output_dir / rel_file_path
        full_dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Image resolver function
        def resolve_image(img_url: str) -> Path | None:
            if not self.image_downloader:
                return None
            return self.image_downloader.process_and_download_image(img_url)

        # Convert HTML to Markdown with local relative links
        markdown_text = self.markdown_converter.convert(
            title=final_title,
            html_content=html_content,
            source_url=source_url,
            current_md_path=full_dest_path,
            image_resolver=resolve_image if self.config.save_images else None,
        )

        with open(full_dest_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        self.state_manager.mark_page_done(
            url=url, title=final_title, local_path=rel_file_path.as_posix(), http_status=200
        )

        if self.on_page_processed:
            self.on_page_processed(url, final_title, full_dest_path)

        # If using HTML Crawler, discover subsequent child links within max_depth
        if isinstance(self.extractor, HtmlCrawlerExtractor) and depth < self.config.max_depth:
            child_links = self.extractor.extract_child_links(html_content, source_url)
            new_items = [
                (child_url, child_title, depth + 1) for child_url, child_title in child_links
            ]
            self.state_manager.add_pages_bulk(new_items)
