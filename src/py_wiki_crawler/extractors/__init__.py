"""Extractors for py-wiki-crawler."""

from py_wiki_crawler.extractors.base import BaseExtractor
from py_wiki_crawler.extractors.html_crawler import HtmlCrawlerExtractor
from py_wiki_crawler.extractors.mediawiki import MediaWikiExtractor

__all__ = ["BaseExtractor", "HtmlCrawlerExtractor", "MediaWikiExtractor"]
