"""
HTML to Markdown converter with intelligent internal link rewriting and image embedding.
"""

import re
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from py_wiki_crawler.utils.path_utils import get_relative_link, title_to_relative_path
from py_wiki_crawler.utils.url_utils import (
    extract_wiki_title_from_url,
    is_crawlable_article_url,
    is_same_domain,
)

UNWANTED_SELECTORS = [
    "nav",
    "footer",
    "header",
    "aside",
    ".mw-editsection",
    ".toc",
    "#toc",
    ".navbox",
    ".wds-global-navigation",
    ".page-header__actions",
    ".license-description",
    ".printfooter",
    ".catlinks",
    ".fandom-community-header",
    ".global-footer",
    "script",
    "style",
    "iframe",
    "noscript",
]


class MarkdownConverter:
    """Converts wiki HTML into clean Markdown with local cross-links and image references."""

    def __init__(self, base_url: str, output_dir: Path):
        self.base_url = base_url.rstrip("/")
        self.output_dir = output_dir

    def clean_html(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Removes unwanted navigation, advertising, and editing elements."""
        for selector in UNWANTED_SELECTORS:
            for element in soup.select(selector):
                element.decompose()
        return soup

    def convert(
        self,
        title: str,
        html_content: str,
        source_url: str,
        current_md_path: Path,
        image_resolver: Callable[[str], Path | None] | None = None,
    ) -> str:
        """
        Converts the provided HTML string into Markdown:
        - Rewrites image URLs to local relative paths if image_resolver is provided.
        - Rewrites internal wiki links to point to the corresponding local .md files.
        - Adds YAML Frontmatter.
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # Locate main content container
        content_container = (
            soup.select_one(".mw-parser-output")
            or soup.select_one("#mw-content-text")
            or soup.select_one("article")
            or soup.select_one("main")
            or soup
        )

        content_container = self.clean_html(content_container)

        # 1. Process images
        for img in content_container.find_all("img"):
            img_src = img.get("src") or img.get("data-src")
            if not img_src:
                continue

            absolute_img_url = urljoin(source_url, img_src)

            if image_resolver:
                local_img_path = image_resolver(absolute_img_url)
                if local_img_path:
                    # Calculate relative link from current markdown file to the image file
                    rel_link = get_relative_link(current_md_path, local_img_path)
                    img["src"] = rel_link
                    if "srcset" in img.attrs:
                        del img["srcset"]
                    if "data-src" in img.attrs:
                        del img["data-src"]

        # 2. Rewrite internal wiki links
        for a_tag in content_container.find_all("a", href=True):
            raw_href = a_tag["href"]
            if raw_href.startswith("#"):
                continue

            abs_target_url = urljoin(source_url, raw_href)

            if is_same_domain(self.base_url, abs_target_url) and is_crawlable_article_url(
                abs_target_url, self.base_url
            ):
                wiki_title = extract_wiki_title_from_url(abs_target_url)
                if wiki_title:
                    target_rel_md = title_to_relative_path(wiki_title)
                    target_full_md = self.output_dir / target_rel_md
                    rel_link = get_relative_link(current_md_path, target_full_md)
                    a_tag["href"] = rel_link

        # 3. Convert HTML to Markdown
        markdown_body = md(
            str(content_container), heading_style="ATX", bullets="-", strip=["script", "style"]
        ).strip()

        # Normalize 3+ newlines to 2
        markdown_body = re.sub(r"\n{3,}", "\n\n", markdown_body)

        # 4. Generate YAML Frontmatter
        clean_title = title.replace('"', '\\"')
        frontmatter = (
            f"---\n"
            f'title: "{clean_title}"\n'
            f'source_url: "{source_url}"\n'
            f'exported_at: "{time.strftime("%Y-%m-%d %H:%M:%S")}"\n'
            f"---\n\n"
        )

        return frontmatter + f"# {title}\n\n" + markdown_body
