#!/usr/bin/env python3
"""
Backwards-compatible wrapper for py-wiki-crawler.
Redirects to the new modular engine in py_wiki_crawler.cli.
"""

from py_wiki_crawler.cli import main

if __name__ == "__main__":
    main()
