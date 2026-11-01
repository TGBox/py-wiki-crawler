"""
py-wiki-crawler: High-performance wiki downloader and markdown converter.
Supports MediaWiki API (Fandom) and fallback recursive HTML crawling.
"""

__version__ = "0.1.1"

from py_wiki_crawler.core.engine import CrawlEngine, EngineConfig

__all__ = ["CrawlEngine", "EngineConfig", "__version__"]

