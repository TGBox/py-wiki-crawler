"""Tests for the image downloader (Referer header, extension detection)."""

from unittest.mock import MagicMock

from py_wiki_crawler.converters.images import ImageDownloader, extension_from_content_type
from py_wiki_crawler.core.rate_limiter import RateLimiter
from py_wiki_crawler.core.state import StateManager


def test_extension_from_content_type():
    assert extension_from_content_type("image/webp") == ".webp"
    assert extension_from_content_type("image/svg+xml; charset=utf-8") == ".svg"
    assert extension_from_content_type("text/html; charset=UTF-8") is None


def test_download_sends_referer_and_uses_served_format(tmp_path):
    session = MagicMock()
    response = session.get.return_value
    response.status_code = 200
    response.content = b"RIFF....WEBP"
    response.headers = {"Content-Type": "image/webp"}

    downloader = ImageDownloader(
        output_dir=tmp_path,
        state_manager=StateManager(tmp_path / ".crawler_state.db"),
        rate_limiter=RateLimiter(base_delay=0),
        session=session,
        referer="https://noita.fandom.com/",
    )
    url = "https://static.wikia.nocookie.net/x/images/8/8f/Amulet.png/revision/latest?cb=1"
    path = downloader.process_and_download_image(url)

    assert session.get.call_args.kwargs["headers"] == {"Referer": "https://noita.fandom.com/"}
    assert path is not None and path.suffix == ".webp" and path.name.startswith("Amulet_")


def test_forbidden_image_is_reported_with_status(tmp_path):
    session = MagicMock()
    session.get.return_value.status_code = 403
    downloader = ImageDownloader(
        output_dir=tmp_path,
        state_manager=StateManager(tmp_path / ".crawler_state.db"),
        rate_limiter=RateLimiter(base_delay=0),
        session=session,
    )
    url = "https://static.wikia.nocookie.net/x/images/8/8f/Amulet.png"
    assert downloader.process_and_download_image(url) is None
    assert downloader.failed_urls[url] == "HTTP 403"
