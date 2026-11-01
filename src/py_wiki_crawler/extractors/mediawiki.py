"""
MediaWiki & Fandom API extractor.
Fast, reliable, and handles site pagination, namespaces, and redirects natively.
"""

import logging
from collections.abc import Iterator
from urllib.parse import quote, urlparse

import requests

from py_wiki_crawler.core.rate_limiter import RateLimiter
from py_wiki_crawler.extractors.base import BaseExtractor
from py_wiki_crawler.utils.url_utils import extract_wiki_title_from_url

logger = logging.getLogger("py_wiki_crawler.mediawiki")


class MediaWikiExtractor(BaseExtractor):
    """Interacts with MediaWiki/Fandom api.php endpoints."""

    def __init__(
        self, base_url: str, api_endpoint: str, session: requests.Session, rate_limiter: RateLimiter
    ):
        self.base_url = base_url.rstrip("/")
        self.api_endpoint = api_endpoint
        self.session = session
        self.rate_limiter = rate_limiter

    @classmethod
    def detect_api(cls, base_url: str, session: requests.Session) -> str | None:
        """Probes standard MediaWiki API endpoint paths."""
        parsed = urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        candidates = [
            f"{base_url.rstrip('/')}/api.php",
            f"{origin}/api.php",
            f"{origin}/w/api.php",
        ]

        for endpoint in candidates:
            try:
                resp = session.get(
                    endpoint,
                    params={"action": "query", "meta": "siteinfo", "format": "json"},
                    timeout=5,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if "query" in data and "general" in data["query"]:
                        logger.info(f"MediaWiki API gefunden: {endpoint}")
                        return endpoint
            except Exception:
                continue

        return None

    def discover_pages(self, max_pages: int | None = None) -> Iterator[tuple[str, str, int]]:
        """Queries the allpages API to list main namespace articles."""
        apfrom = None
        count = 0

        logger.info("Rufe Artikelliste über die MediaWiki API ab...")

        while True:
            params = {
                "action": "query",
                "list": "allpages",
                "aplimit": "500",
                "apnamespace": "0",  # Main article namespace
                "format": "json",
            }
            if apfrom:
                params["apcontinue"] = apfrom

            current_params = dict(params)
            resp = self.rate_limiter.execute_with_retry(
                lambda p=current_params: self.session.get(self.api_endpoint, params=p, timeout=15),
                description="Artikelliste (allpages) abrufen",
            )

            if resp.status_code != 200:
                logger.error(f"Fehler beim Abruf von allpages: Status {resp.status_code}")
                break

            data = resp.json()
            pages = data.get("query", {}).get("allpages", [])
            for page in pages:
                title = page["title"]
                article_url = f"{self.base_url}/wiki/{quote(title.replace(' ', '_'))}"
                yield (article_url, title, 0)
                count += 1
                if max_pages and count >= max_pages:
                    return

            if "continue" in data and "apcontinue" in data["continue"]:
                apfrom = data["continue"]["apcontinue"]
            else:
                break

        logger.info(f"Insgesamt {count} Artikel über API entdeckt.")

    def fetch_page_content(self, url_or_title: str) -> tuple[str, str, str] | None:
        """Parses a page's wikitext into HTML using action=parse."""
        if url_or_title.startswith("http://") or url_or_title.startswith("https://"):
            title = extract_wiki_title_from_url(url_or_title) or url_or_title
            source_url = url_or_title
        else:
            title = url_or_title
            source_url = f"{self.base_url}/wiki/{quote(title.replace(' ', '_'))}"

        params = {
            "action": "parse",
            "page": title,
            "prop": "text",
            "format": "json",
            "disableeditsection": "1",
            "redirects": "1",
        }

        try:
            resp = self.rate_limiter.execute_with_retry(
                lambda: self.session.get(self.api_endpoint, params=params, timeout=15),
                description=f"Parse {title}",
            )

            if resp.status_code != 200:
                logger.warning(f"Konnte Seite nicht abrufen ({resp.status_code}): {title}")
                return None

            data = resp.json()
            if "parse" not in data:
                logger.warning(
                    f"API parse Antwort unvollständig für '{title}': {data.get('error')}"
                )
                return None

            actual_title = data["parse"].get("title", title)
            html_text = data["parse"]["text"]["*"]

            return (actual_title, html_text, source_url)

        except Exception as e:
            logger.error(f"Fehler beim API-Parse von '{title}': {e}")
            return None
