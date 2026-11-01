"""
Generic HTML BFS crawler extractor.
Fallback for non-MediaWiki wikis or sites without API access.
"""

import logging
from collections.abc import Iterator
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from py_wiki_crawler.core.rate_limiter import RateLimiter
from py_wiki_crawler.extractors.base import BaseExtractor
from py_wiki_crawler.utils.url_utils import (
    extract_wiki_title_from_url,
    is_crawlable_article_url,
    normalize_url,
)

logger = logging.getLogger("py_wiki_crawler.html_crawler")


class HtmlCrawlerExtractor(BaseExtractor):
    """Recursively crawls HTML wikis using Breadth-First Search (BFS)."""

    def __init__(
        self,
        base_url: str,
        session: requests.Session,
        rate_limiter: RateLimiter,
        max_depth: int = 5,
    ):
        self.base_url = normalize_url(base_url)
        self.session = session
        self.rate_limiter = rate_limiter
        self.max_depth = max_depth

    def discover_pages(self, max_pages: int | None = None) -> Iterator[tuple[str, str, int]]:
        """
        Yields the start page. Subsequent pages are discovered dynamically during crawling.
        """
        initial_title = extract_wiki_title_from_url(self.base_url) or "Index"
        yield (self.base_url, initial_title, 0)

    def fetch_page_content(self, url_or_title: str) -> tuple[str, str, str] | None:
        """Downloads the HTML document from url_or_title."""
        url = url_or_title
        try:
            resp = self.rate_limiter.execute_with_retry(
                lambda: self.session.get(url, timeout=15), description=f"HTML-Abruf {url}"
            )

            if resp.status_code != 200:
                logger.warning(f"Status {resp.status_code} für URL: {url}")
                return None

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                logger.debug(f"Überspringe Nicht-HTML Antwort ({content_type}): {url}")
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            h1 = soup.find("h1")
            title = (
                h1.get_text(strip=True)
                if h1
                else (soup.title.string.strip() if soup.title and soup.title.string else "")
            )
            if not title:
                title = extract_wiki_title_from_url(url) or "Unbenannt"

            return (title, resp.text, url)

        except Exception as e:
            logger.error(f"Fehler beim Laden von {url}: {e}")
            return None

    def extract_child_links(self, html_content: str, current_url: str) -> list[tuple[str, str]]:
        """
        Extracts valid crawlable internal links from an HTML document.
        Returns a list of (child_url, child_title).
        """
        soup = BeautifulSoup(html_content, "html.parser")
        discovered: list[tuple[str, str]] = []
        seen: set[str] = set()

        for a_tag in soup.find_all("a", href=True):
            raw_href = a_tag["href"]
            if raw_href.startswith("#"):
                continue

            absolute_url = normalize_url(urljoin(current_url, raw_href))
            if absolute_url in seen:
                continue

            if is_crawlable_article_url(absolute_url, self.base_url):
                seen.add(absolute_url)
                link_title = (
                    a_tag.get_text(strip=True)
                    or extract_wiki_title_from_url(absolute_url)
                    or "Link"
                )
                discovered.append((absolute_url, link_title))

        return discovered
