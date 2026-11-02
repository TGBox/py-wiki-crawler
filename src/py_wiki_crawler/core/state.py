"""
State management and checkpointing using SQLite.
Enables resumable crawling and asset deduplication across runs.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Any


class StateManager:
    """Manages crawl checkpoints and asset records in a local SQLite database."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pages (
                        url TEXT PRIMARY KEY,
                        title TEXT,
                        local_path TEXT,
                        status TEXT DEFAULT 'pending',
                        depth INTEGER DEFAULT 0,
                        http_status INTEGER,
                        error_message TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS images (
                        source_url TEXT PRIMARY KEY,
                        sha256 TEXT,
                        local_path TEXT,
                        status TEXT DEFAULT 'done',
                        size_bytes INTEGER,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_sha256 ON images(sha256)")
                conn.commit()

    def set_metadata(self, key: str, value: str) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO metadata (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                    """,
                    (key, value),
                )
                conn.commit()

    def get_metadata(self, key: str) -> str | None:
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
                return row["value"] if row else None

    def add_page(self, url: str, title: str, depth: int = 0) -> bool:
        """Adds a page to the queue if not already present. Returns True if newly added."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO pages (url, title, status, depth)
                    VALUES (?, ?, 'pending', ?)
                    """,
                    (url, title, depth),
                )
                conn.commit()
                return cursor.rowcount > 0

    def add_pages_bulk(self, pages: list[tuple[str, str, int]]) -> int:
        """Bulk adds pages (url, title, depth). Returns count of newly inserted pages."""
        if not pages:
            return 0
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    """
                    INSERT OR IGNORE INTO pages (url, title, status, depth)
                    VALUES (?, ?, 'pending', ?)
                    """,
                    pages,
                )
                conn.commit()
                return cursor.rowcount

    def requeue_failed_pages(self) -> int:
        """Puts all failed pages back into the queue. Returns the number of requeued pages."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "UPDATE pages SET status = 'pending' WHERE status = 'failed'"
                )
                conn.commit()
                return cursor.rowcount

    def requeue_all_pages(self) -> int:
        """Puts every known page back into the queue (full re-download)."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("UPDATE pages SET status = 'pending'")
                conn.commit()
                return cursor.rowcount

    def get_pending_pages(self, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            with self._get_connection() as conn:
                query = (
                    "SELECT url, title, depth FROM pages "
                    "WHERE status = 'pending' ORDER BY depth ASC"
                )
                if limit:
                    query += f" LIMIT {limit}"
                rows = conn.execute(query).fetchall()
                return [dict(r) for r in rows]

    def is_page_done(self, url: str) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute("SELECT status FROM pages WHERE url = ?", (url,)).fetchone()
                return bool(row and row["status"] == "done")

    def mark_page_done(self, url: str, title: str, local_path: str, http_status: int = 200) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO pages (url, title, local_path, status, http_status, updated_at)
                    VALUES (?, ?, ?, 'done', ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(url) DO UPDATE SET
                        title = excluded.title,
                        local_path = excluded.local_path,
                        status = 'done',
                        http_status = excluded.http_status,
                        error_message = NULL,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (url, title, local_path, http_status),
                )
                conn.commit()

    def mark_page_failed(
        self, url: str, error_message: str, http_status: int | None = None
    ) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE pages
                    SET status = 'failed',
                        error_message = ?,
                        http_status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE url = ?
                """,
                    (error_message, http_status, url),
                )
                conn.commit()

    def get_image_by_url(self, source_url: str) -> dict[str, Any] | None:
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM images WHERE source_url = ?", (source_url,)
                ).fetchone()
                return dict(row) if row else None

    def get_image_by_hash(self, sha256_hash: str) -> dict[str, Any] | None:
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM images WHERE sha256 = ? AND status = 'done'", (sha256_hash,)
                ).fetchone()
                return dict(row) if row else None

    def record_image(
        self,
        source_url: str,
        sha256_hash: str,
        local_path: str,
        size_bytes: int,
        status: str = "done",
    ) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO images (
                        source_url, sha256, local_path, status, size_bytes, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(source_url) DO UPDATE SET
                        sha256 = excluded.sha256,
                        local_path = excluded.local_path,
                        status = excluded.status,
                        size_bytes = excluded.size_bytes,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (source_url, sha256_hash, local_path, status, size_bytes),
                )
                conn.commit()

    def get_stats(self) -> dict[str, int]:
        with self._lock:
            with self._get_connection() as conn:
                total_pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
                done_pages = conn.execute(
                    "SELECT COUNT(*) FROM pages WHERE status = 'done'"
                ).fetchone()[0]
                failed_pages = conn.execute(
                    "SELECT COUNT(*) FROM pages WHERE status = 'failed'"
                ).fetchone()[0]
                pending_pages = conn.execute(
                    "SELECT COUNT(*) FROM pages WHERE status = 'pending'"
                ).fetchone()[0]
                total_images = conn.execute(
                    "SELECT COUNT(*) FROM images WHERE status = 'done'"
                ).fetchone()[0]

                return {
                    "total_pages": total_pages,
                    "done_pages": done_pages,
                    "failed_pages": failed_pages,
                    "pending_pages": pending_pages,
                    "total_images": total_images,
                }
