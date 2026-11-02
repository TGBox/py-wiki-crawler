"""
Background QThread worker for executing wiki crawls without freezing the Qt GUI.
"""

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from py_wiki_crawler.core.engine import CrawlEngine, EngineConfig


class CrawlWorker(QObject):
    """Worker object that runs inside a QThread to execute CrawlEngine operations."""

    signal_started = Signal()
    signal_page_discovered = Signal(str, str)
    signal_page_processed = Signal(str, str, str)  # url, title, local_path
    signal_page_failed = Signal(str, str, str)  # url, title, error
    signal_log = Signal(str, str)  # message, level (info, warning, error, success)
    signal_finished = Signal(dict)  # stats dictionary
    signal_error = Signal(str)

    def __init__(self, config: EngineConfig):
        super().__init__()
        self.config = config
        self.engine: CrawlEngine | None = None

    def run(self) -> None:
        """Executes the crawl."""
        self.signal_started.emit()
        self.signal_log.emit(f"Initialisiere Engine für: {self.config.base_url}", "info")

        try:
            self.engine = CrawlEngine(self.config)

            def on_discovered(url: str, title: str) -> None:
                self.signal_page_discovered.emit(url, title)

            def on_processed(url: str, title: str, local_path: Path) -> None:
                self.signal_page_processed.emit(url, title, local_path.as_posix())
                self.signal_log.emit(f"Gespeichert: {title}", "success")

            def on_failed(url: str, title: str, error: str) -> None:
                self.signal_page_failed.emit(url, title, error)
                self.signal_log.emit(f"Fehler bei '{title}': {error}", "error")

            self.engine.on_page_discovered = on_discovered
            self.engine.on_page_processed = on_processed
            self.engine.on_page_failed = on_failed
            self.engine.on_log = lambda message, level: self.signal_log.emit(message, level)

            stats = self.engine.run()
            self.signal_finished.emit(stats)

        except Exception as e:
            self.signal_error.emit(str(e))
            self.signal_log.emit(f"Kritischer Fehler: {e}", "error")

    def stop(self) -> None:
        """Cancels the running crawl engine."""
        if self.engine:
            self.engine.stop()
            self.signal_log.emit("Abbruch angefordert. Schließe laufende Aufgaben ab...", "warning")
