"""
Base interface for wiki extractors.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator


class BaseExtractor(ABC):
    """Abstract base class for extracting content from wikis."""

    @abstractmethod
    def discover_pages(self, max_pages: int | None = None) -> Iterator[tuple[str, str, int]]:
        """
        Discovers pages to scrape.
        Yields tuples of (url, title, depth).
        """
        pass

    @abstractmethod
    def fetch_page_content(self, url_or_title: str) -> tuple[str, str, str] | None:
        """
        Fetches the rendered HTML content for a page.
        Returns (title, html_content, source_url) or None if fetch fails.
        """
        pass
