"""
Image downloading, URL cleaning, and SHA-256 deduplication for py-wiki-crawler.
"""

import hashlib
import logging
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from py_wiki_crawler.core.rate_limiter import RateLimiter
from py_wiki_crawler.core.state import StateManager
from py_wiki_crawler.utils.path_utils import sanitize_path_segment
from py_wiki_crawler.utils.url_utils import clean_image_url

logger = logging.getLogger("py_wiki_crawler.images")


class ImageDownloader:
    """Manages downloading, deduplicating, and storing wiki reference images."""

    def __init__(
        self,
        output_dir: Path,
        state_manager: StateManager,
        rate_limiter: RateLimiter | None = None,
        session: requests.Session | None = None,
    ):
        self.output_dir = output_dir
        self.images_dir = output_dir / "assets" / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.state_manager = state_manager
        self.rate_limiter = rate_limiter or RateLimiter(base_delay=0.1)
        self.session = session or requests.Session()
        # URLs that already failed in this run (avoids hammering broken URLs on every page)
        self.failed_urls: set[str] = set()

    def process_and_download_image(self, raw_img_url: str) -> Path | None:
        """
        Processes an image URL:
        1. Cleans thumbnail/scaling parameters to reach full resolution.
        2. Checks state manager if already downloaded (URL match or Hash match).
        3. Downloads stream, calculates SHA-256.
        4. Reuses file if duplicate hash exists; otherwise saves to assets/images/.
        5. Returns the local Path of the saved image relative to output_dir.
        """
        if raw_img_url.startswith("data:"):
            return None

        full_url = clean_image_url(raw_img_url)
        if full_url in self.failed_urls:
            return None

        # Check by URL first
        existing_record = self.state_manager.get_image_by_url(full_url)
        if existing_record and existing_record.get("status") == "done":
            local_rel_str = existing_record["local_path"]
            local_file = self.output_dir / local_rel_str
            if local_file.exists():
                return local_file

        # Download stream with retry
        try:
            resp = self.rate_limiter.execute_with_retry(
                lambda: self.session.get(full_url, stream=True, timeout=15),
                description=f"Bild-Download {full_url}",
            )
            if resp.status_code != 200:
                logger.warning(f"Bild konnte nicht geladen werden ({resp.status_code}): {full_url}")
                self.failed_urls.add(full_url)
                return None

            content = resp.content
            if not content:
                self.failed_urls.add(full_url)
                return None

            sha256_hash = hashlib.sha256(content).hexdigest()

            # Check if this exact hash already exists in another file
            existing_hash_record = self.state_manager.get_image_by_hash(sha256_hash)
            if existing_hash_record:
                local_rel_str = existing_hash_record["local_path"]
                local_file = self.output_dir / local_rel_str
                if local_file.exists():
                    # Record this URL pointing to existing file
                    self.state_manager.record_image(
                        source_url=full_url,
                        sha256_hash=sha256_hash,
                        local_path=local_rel_str,
                        size_bytes=len(content),
                    )
                    return local_file

            # Determine file extension and name
            parsed_path = unquote(urlparse(full_url).path)
            orig_filename = Path(parsed_path).name or "image.png"
            stem = sanitize_path_segment(Path(orig_filename).stem)
            ext = Path(orig_filename).suffix.lower()
            if not ext or ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}:
                content_type = resp.headers.get("Content-Type", "")
                if "jpeg" in content_type:
                    ext = ".jpg"
                elif "gif" in content_type:
                    ext = ".gif"
                elif "svg" in content_type:
                    ext = ".svg"
                elif "webp" in content_type:
                    ext = ".webp"
                else:
                    ext = ".png"

            # Create collision-safe filename: {stem}_{hash[:8]}{ext}
            target_filename = f"{stem}_{sha256_hash[:8]}{ext}"
            target_path = self.images_dir / target_filename

            with open(target_path, "wb") as f:
                f.write(content)

            rel_path_to_output = target_path.relative_to(self.output_dir)

            self.state_manager.record_image(
                source_url=full_url,
                sha256_hash=sha256_hash,
                local_path=rel_path_to_output.as_posix(),
                size_bytes=len(content),
            )

            return target_path

        except Exception as e:
            logger.warning(f"Fehler beim Download von Bild {full_url}: {e}")
            self.failed_urls.add(full_url)
            return None
