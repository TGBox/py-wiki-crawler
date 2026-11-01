"""
URL utilities for py-wiki-crawler.
Provides URL normalization, scope validation, and wiki title extraction.
"""

import re
from urllib.parse import parse_qs, unquote, urlparse

# Extensions to ignore when crawling HTML pages (not articles)
IGNORE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".bmp",
    ".ico",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".mp3",
    ".ogg",
    ".wav",
    ".mp4",
    ".webm",
    ".css",
    ".js",
    ".json",
    ".xml",
}

# URL query parameters and paths indicating edit/history/special pages
IGNORE_PATTERNS = [
    r"[?&]action=(edit|history|raw|delete|protect|render|info)",
    r"[?&]diff=",
    r"[?&]oldid=",
    r"/wiki/Special:",
    r"/wiki/Spezial:",
    r"/wiki/Talk:",
    r"/wiki/Diskussion:",
    r"/wiki/User:",
    r"/wiki/Benutzer:",
    r"/wiki/User_talk:",
    r"/wiki/File:",
    r"/wiki/Datei:",
    r"/wiki/MediaWiki:",
    r"/wiki/Template:",
    r"/wiki/Vorlage:",
    r"/wiki/Category:",
    r"/wiki/Kategorie:",
    r"[?&]feed=",
    r"#",
]


def normalize_url(url: str) -> str:
    """Strips query fragments (#) and trailing slashes for consistent comparison."""
    parsed = urlparse(url)
    clean = parsed._replace(fragment="")
    clean_url_str = clean.geturl()
    if clean_url_str.endswith("/") and clean.path != "/":
        clean_url_str = clean_url_str[:-1]
    return clean_url_str


def is_same_domain(base_url: str, target_url: str) -> bool:
    """Checks whether target_url belongs to the same network domain as base_url."""
    base_netloc = urlparse(base_url).netloc.lower()
    target_netloc = urlparse(target_url).netloc.lower()
    return base_netloc == target_netloc


def is_crawlable_article_url(url: str, base_url: str) -> bool:
    """
    Checks if a URL should be crawled as an article:
    - Same domain
    - Not an image/archive file extension
    - Not a special/edit/history page
    """
    if not is_same_domain(base_url, url):
        return False

    parsed = urlparse(url)
    path = parsed.path.lower()

    if any(path.endswith(ext) for ext in IGNORE_EXTENSIONS):
        return False

    for pattern in IGNORE_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return False

    return True


def extract_wiki_title_from_url(url: str) -> str | None:
    """
    Extracts the article title from a wiki URL.
    Examples:
      https://example.fandom.com/wiki/Master_Sword -> 'Master Sword'
      https://example.org/index.php?title=Master_Sword -> 'Master Sword'
      https://example.org/wiki/Item/Sword -> 'Item/Sword'
    """
    parsed = urlparse(url)

    # Check query param first (index.php?title=...)
    qs = parse_qs(parsed.query)
    if "title" in qs and qs["title"]:
        title_str = qs["title"][0]
        return unquote(title_str).replace("_", " ")

    # Check path pattern /wiki/...
    path = parsed.path
    wiki_prefix = "/wiki/"
    if wiki_prefix in path:
        relative = path.split(wiki_prefix, 1)[1]
        if relative:
            return unquote(relative).replace("_", " ")

    return None


def clean_image_url(image_url: str) -> str:
    """
    Strips Fandom CDN scaling parameters and thumbnail prefixes
    to obtain the full-resolution original image URL.

    Examples:
      Fandom:
      .../image.png/revision/latest/scale-to-width-down/350?cb=123
      -> .../image.png

      Standard MediaWiki:
      .../thumb/a/ab/File.png/300px-File.png
      -> .../a/ab/File.png
    """
    url = normalize_url(image_url)

    # MediaWiki standard thumb pattern: /thumb/x/xx/File.ext/NNNpx-File.ext
    thumb_match = re.match(r"^(.*?)/thumb/([a-f0-9]/[a-f0-9]{2}/[^/]+)/[^/]+$", url)
    if thumb_match:
        return f"{thumb_match.group(1)}/{thumb_match.group(2)}"

    # Fandom revision scaling pattern: .../filename.ext/revision/latest/...
    fandom_match = re.match(
        r"^(.*?/(?:images|thumb)/[^\?]+?\.(?:png|jpg|jpeg|gif|webp|svg))(?:/revision/.*|/scale-to-width-down/.*)?",
        url,
        re.IGNORECASE,
    )
    if fandom_match:
        return fandom_match.group(1)

    return url
