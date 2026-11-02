"""Tests for the MediaWiki extractor URL/title handling."""

from unittest.mock import MagicMock

from py_wiki_crawler.extractors.mediawiki import MediaWikiExtractor


def _make_extractor(base_url: str, siteinfo: dict | None) -> MediaWikiExtractor:
    session = MagicMock()
    if siteinfo is None:
        session.get.side_effect = Exception("offline")
    else:
        session.get.return_value.json.return_value = {"query": {"general": siteinfo}}
    return MediaWikiExtractor(base_url, "https://x.fandom.com/api.php", session, MagicMock())


def test_article_urls_ignore_start_page_in_base_url():
    ext = _make_extractor(
        "https://x.fandom.com/wiki/Main_Page",
        {"server": "https://x.fandom.com", "articlepath": "/wiki/$1"},
    )
    url = ext._article_url("Acid Cloud")
    assert url == "https://x.fandom.com/wiki/Acid_Cloud"
    assert ext._title_from_url(url) == "Acid Cloud"


def test_protocol_relative_server_and_subpages():
    ext = _make_extractor(
        "https://wiki.example.org/w/Start",
        {"server": "//wiki.example.org", "articlepath": "/w/$1"},
    )
    assert ext._title_from_url("https://wiki.example.org/w/Item/Sword") == "Item/Sword"


def test_fallback_when_siteinfo_unavailable():
    ext = _make_extractor("https://x.fandom.com/wiki/Main_Page", None)
    assert ext._article_url("Acid") == "https://x.fandom.com/wiki/Acid"
