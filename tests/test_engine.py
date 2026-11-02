"""Tests for re-run behaviour of the CrawlEngine (skip done, retry failed)."""

from collections.abc import Iterator
from unittest.mock import patch

from py_wiki_crawler.core.engine import CrawlEngine, EngineConfig
from py_wiki_crawler.extractors.base import BaseExtractor


class FakeExtractor(BaseExtractor):
    """Returns two pages; 'B' fails until fail_b is switched off."""

    def __init__(self) -> None:
        self.fail_b = True
        self.fetched: list[str] = []

    def discover_pages(self, max_pages: int | None = None) -> Iterator[tuple[str, str, int]]:
        yield ("https://w.org/wiki/A", "A", 0)
        yield ("https://w.org/wiki/B", "B", 0)

    def fetch_page_content(self, url_or_title: str) -> tuple[str, str, str] | None:
        self.fetched.append(url_or_title)
        if url_or_title.endswith("/B") and self.fail_b:
            return None
        title = url_or_title.rsplit("/", 1)[1]
        return (title, f"<div class='mw-parser-output'><p>{title}</p></div>", url_or_title)


def _make_engine(tmp_path, extractor: FakeExtractor, force: bool = False) -> CrawlEngine:
    config = EngineConfig(
        base_url="https://w.org", output_dir=tmp_path, save_images=False, force_refresh=force
    )
    with patch.object(CrawlEngine, "_init_extractor", return_value=extractor):
        return CrawlEngine(config)


def test_rerun_only_retries_failed_pages(tmp_path):
    extractor = FakeExtractor()
    stats = _make_engine(tmp_path, extractor).run()
    assert stats["done_pages"] == 1
    assert stats["failed_pages"] == 1

    extractor.fail_b = False
    extractor.fetched.clear()
    stats = _make_engine(tmp_path, extractor).run()

    assert extractor.fetched == ["https://w.org/wiki/B"]
    assert stats["done_pages"] == 2
    assert stats["failed_pages"] == 0


def test_force_refresh_reloads_everything(tmp_path):
    extractor = FakeExtractor()
    extractor.fail_b = False
    _make_engine(tmp_path, extractor).run()

    extractor.fetched.clear()
    _make_engine(tmp_path, extractor, force=True).run()
    assert sorted(extractor.fetched) == ["https://w.org/wiki/A", "https://w.org/wiki/B"]


class RedirectExtractor(FakeExtractor):
    """'a' is a redirect resolving to the same article as 'A'."""

    def discover_pages(self, max_pages: int | None = None) -> Iterator[tuple[str, str, int]]:
        yield ("https://w.org/wiki/A", "A", 0)
        yield ("https://w.org/wiki/a", "a", 0)

    def fetch_page_content(self, url_or_title: str) -> tuple[str, str, str] | None:
        self.fetched.append(url_or_title)
        return ("A", "<div class='mw-parser-output'><p>A</p></div>", url_or_title)


def test_redirects_are_skipped_and_not_retried(tmp_path):
    extractor = RedirectExtractor()
    stats = _make_engine(tmp_path, extractor).run()
    assert stats["done_pages"] == 1
    assert stats["failed_pages"] == 0

    extractor.fetched.clear()
    _make_engine(tmp_path, extractor).run()
    assert extractor.fetched == []
