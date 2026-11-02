"""
Main application window for py-wiki-crawler GUI.
Supports Fullscreen mode, Windowed mode, live statistics, and background crawling.
"""

import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTime, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QFont,
    QKeySequence,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from py_wiki_crawler import __version__
from py_wiki_crawler.core.engine import EngineConfig
from py_wiki_crawler.gui.worker import CrawlWorker


class MetricCard(QFrame):
    """Visual metric display card."""

    def __init__(self, title: str, initial_value: str = "0", color: str = "#2563eb"):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            MetricCard {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 500;")

        self.lbl_value = QLabel(initial_value)
        self.lbl_value.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: 700;")

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)

    def set_value(self, value: str) -> None:
        self.lbl_value.setText(value)


class MainWindow(QMainWindow):
    """Main window with full support for windowed mode and fullscreen mode."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"py-wiki-crawler v{__version__} — Wiki Downloader & Archivierer")
        self.resize(1024, 760)
        self.setMinimumSize(800, 600)

        # State tracking
        self.thread: QThread | None = None
        self.worker: CrawlWorker | None = None
        self.start_timestamp: float | None = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_timer)

        self.total_discovered_pages = 0
        self.processed_pages_count = 0
        self.images_count = 0
        self.failed_count = 0

        self._setup_ui()
        self._setup_menus()
        self._setup_shortcuts()
        self._apply_styles()

    def _setup_menus(self) -> None:
        """Sets up the menu bar with Windowed / Fullscreen controls."""
        menubar = self.menuBar()

        # Datei Menu
        file_menu = menubar.addMenu("Datei")
        exit_action = QAction("Beenden", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Ansicht Menu (Fullscreen / Windowed mode toggle)
        view_menu = menubar.addMenu("Ansicht")

        self.action_fullscreen = QAction("Vollbildmodus umschalten", self)
        self.action_fullscreen.setShortcut(QKeySequence("F11"))
        self.action_fullscreen.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(self.action_fullscreen)

        self.action_windowed = QAction("Fenstermodus erzwingen", self)
        self.action_windowed.setShortcut(QKeySequence("Esc"))
        self.action_windowed.triggered.connect(self.set_windowed_mode)
        view_menu.addAction(self.action_windowed)

        # Hilfe Menu
        help_menu = menubar.addMenu("Hilfe")
        about_action = QAction("Über py-wiki-crawler", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_shortcuts(self) -> None:
        """Configures keyboard shortcuts."""
        # F11 is already mapped to action_fullscreen
        pass

    def _setup_ui(self) -> None:
        """Builds the main user interface."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # 1. Header Toolbar
        header_layout = QHBoxLayout()
        title_label = QLabel("Wiki Offline Vault Downloader")
        title_label.setStyleSheet("font-size: 20px; font-weight: 700; color: #f8fafc;")

        subtitle_label = QLabel("MediaWiki API & Rekursiver Fallback-Crawler")
        subtitle_label.setStyleSheet("font-size: 13px; color: #94a3b8; margin-left: 8px;")

        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        header_layout.addStretch()

        # Dedicated Fullscreen / Windowed toggle button
        self.btn_toggle_fullscreen = QPushButton("⛶ Vollbildmodus (F11)")
        self.btn_toggle_fullscreen.setToolTip("Wechselt zwischen Vollbild- und Fenstermodus (F11)")
        self.btn_toggle_fullscreen.clicked.connect(self.toggle_fullscreen)
        header_layout.addWidget(self.btn_toggle_fullscreen)

        main_layout.addLayout(header_layout)

        # 2. Settings & Input Group
        input_group = QGroupBox("Crawl-Konfiguration")
        input_layout = QGridLayout(input_group)
        input_layout.setSpacing(10)

        # Wiki URL
        input_layout.addWidget(QLabel("Wiki-URL:"), 0, 0)
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText(
            "z.B. https://hollowknight.fandom.com oder https://wiki.archlinux.org"
        )
        input_layout.addWidget(self.txt_url, 0, 1, 1, 2)

        # Output Directory
        input_layout.addWidget(QLabel("Zielordner:"), 1, 0)
        self.txt_output_dir = QLineEdit(str(Path("wiki_export").resolve()))
        self.btn_browse = QPushButton("Durchsuchen...")
        self.btn_browse.clicked.connect(self._browse_output_dir)
        input_layout.addWidget(self.txt_output_dir, 1, 1)
        input_layout.addWidget(self.btn_browse, 1, 2)

        # Options Row
        options_layout = QHBoxLayout()
        options_layout.setSpacing(16)

        # Delay
        lbl_delay = QLabel("Verzögerung (Sek.):")
        self.spn_delay = QDoubleSpinBox()
        self.spn_delay.setRange(0.0, 10.0)
        self.spn_delay.setSingleStep(0.1)
        self.spn_delay.setValue(0.4)
        options_layout.addWidget(lbl_delay)
        options_layout.addWidget(self.spn_delay)

        # Max Pages
        self.chk_limit_pages = QCheckBox("Max. Seiten:")
        self.chk_limit_pages.toggled.connect(lambda checked: self.spn_max_pages.setEnabled(checked))
        self.spn_max_pages = QSpinBox()
        self.spn_max_pages.setRange(1, 1000000)
        self.spn_max_pages.setValue(50)
        self.spn_max_pages.setEnabled(False)
        options_layout.addWidget(self.chk_limit_pages)
        options_layout.addWidget(self.spn_max_pages)

        # Max Depth (for HTML crawler)
        lbl_depth = QLabel("Max. Klicktiefe:")
        self.spn_max_depth = QSpinBox()
        self.spn_max_depth.setRange(1, 30)
        self.spn_max_depth.setValue(5)
        options_layout.addWidget(lbl_depth)
        options_layout.addWidget(self.spn_max_depth)

        # Images Checkbox
        self.chk_images = QCheckBox("Bilder herunterladen")
        self.chk_images.setChecked(True)
        options_layout.addWidget(self.chk_images)

        # Resume Checkbox
        self.chk_resume = QCheckBox("Fortsetzen (Resume)")
        self.chk_resume.setToolTip(
            "Setzt einen unterbrochenen Crawl anhand der SQLite-Datenbank fort"
        )
        options_layout.addWidget(self.chk_resume)

        options_layout.addStretch()
        input_layout.addLayout(options_layout, 2, 0, 1, 3)

        main_layout.addWidget(input_group)

        # 3. Actions Row
        actions_layout = QHBoxLayout()
        self.btn_start = QPushButton("▶ Crawl starten")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.setStyleSheet("""
            QPushButton#btn_start {
                background-color: #16a34a;
                color: white;
                font-size: 14px;
                font-weight: 700;
                padding: 10px 24px;
                border-radius: 6px;
                border: none;
            }
            QPushButton#btn_start:hover {
                background-color: #15803d;
            }
            QPushButton#btn_start:disabled {
                background-color: #334155;
                color: #64748b;
            }
        """)
        self.btn_start.clicked.connect(self.start_crawl)

        self.btn_stop = QPushButton("⏹ Abbrechen")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                font-size: 14px;
                font-weight: 600;
                padding: 10px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #64748b;
            }
        """)
        self.btn_stop.clicked.connect(self.stop_crawl)

        self.btn_open_folder = QPushButton("📁 Ordner öffnen")
        self.btn_open_folder.clicked.connect(self._open_export_folder)

        actions_layout.addWidget(self.btn_start)
        actions_layout.addWidget(self.btn_stop)
        actions_layout.addWidget(self.btn_open_folder)
        actions_layout.addStretch()
        main_layout.addLayout(actions_layout)

        # 4. Progress and Metrics
        metrics_layout = QHBoxLayout()
        self.card_pages = MetricCard("Exportierte Seiten", "0", "#38bdf8")
        self.card_images = MetricCard("Heruntergeladene Grafiken", "0", "#4ade80")
        self.card_failed = MetricCard("Fehlgeschlagen", "0", "#f87171")
        self.card_time = MetricCard("Laufzeit", "00:00:00", "#fbbf24")

        metrics_layout.addWidget(self.card_pages)
        metrics_layout.addWidget(self.card_images)
        metrics_layout.addWidget(self.card_failed)
        metrics_layout.addWidget(self.card_time)
        main_layout.addLayout(metrics_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #334155;
                border-radius: 6px;
                background-color: #1e293b;
                height: 22px;
                text-align: center;
                color: #f8fafc;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 5px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        # 5. Live Log Area
        log_group = QGroupBox("Aktivitäts-Protokoll")
        log_layout = QVBoxLayout(log_group)
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFont(QFont("Consolas", 10))
        self.txt_log.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        log_layout.addWidget(self.txt_log)
        main_layout.addWidget(log_group, stretch=1)

        # Status Bar
        self.statusBar().showMessage("Bereit")

    def _apply_styles(self) -> None:
        """Applies overall modern dark theme."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b1120;
            }
            QWidget {
                color: #f8fafc;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            QGroupBox {
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 10px;
                font-weight: 600;
                color: #cbd5e1;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #f8fafc;
                padding: 6px 10px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #3b82f6;
            }
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #475569;
                border-radius: 6px;
                color: #f8fafc;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
            QMenuBar {
                background-color: #0f172a;
                color: #cbd5e1;
                border-bottom: 1px solid #1e293b;
            }
            QMenuBar::item:selected {
                background-color: #1e293b;
            }
            QMenu {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
                color: white;
            }
            QStatusBar {
                background-color: #0f172a;
                color: #94a3b8;
                border-top: 1px solid #1e293b;
            }
        """)

    # =========================================================================
    # Fullscreen & Windowed Mode Handlers
    # =========================================================================
    def toggle_fullscreen(self) -> None:
        """Toggles between fullscreen mode and windowed mode."""
        if self.isFullScreen():
            self.set_windowed_mode()
        else:
            self.set_fullscreen_mode()

    def set_fullscreen_mode(self) -> None:
        """Enters fullscreen mode."""
        self.showFullScreen()
        self.btn_toggle_fullscreen.setText("🗗 Fenstermodus (F11)")
        self.action_fullscreen.setText("Fenstermodus aktivieren")
        self.statusBar().showMessage(
            "Vollbildmodus aktiviert (Drücke F11 oder Esc zum Verlassen)", 3000
        )

    def set_windowed_mode(self) -> None:
        """Enters normal windowed mode."""
        self.showNormal()
        self.btn_toggle_fullscreen.setText("⛶ Vollbildmodus (F11)")
        self.action_fullscreen.setText("Vollbildmodus aktivieren")
        self.statusBar().showMessage("Fenstermodus aktiviert", 2000)

    def keyPressEvent(self, event) -> None:
        """Handles Escape key to exit fullscreen."""
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.set_windowed_mode()
            event.accept()
        else:
            super().keyPressEvent(event)

    # =========================================================================
    # Crawl Execution & Threading
    # =========================================================================
    def start_crawl(self) -> None:
        """Starts the crawling worker thread."""
        url = self.txt_url.text().strip()
        if not url:
            QMessageBox.warning(
                self, "Eingabe erforderlich", "Bitte gib eine gültige Wiki-Start-URL an!"
            )
            return

        out_dir = Path(self.txt_output_dir.text().strip())

        max_p = self.spn_max_pages.value() if self.chk_limit_pages.isChecked() else None

        config = EngineConfig(
            base_url=url,
            output_dir=out_dir,
            delay=self.spn_delay.value(),
            max_pages=max_p,
            max_depth=self.spn_max_depth.value(),
            save_images=self.chk_images.isChecked(),
            resume=self.chk_resume.isChecked(),
        )

        # Reset counters
        self.processed_pages_count = 0
        self.total_discovered_pages = 0
        self.images_count = 0
        self.failed_count = 0
        self.card_pages.set_value("0")
        self.card_images.set_value("0")
        self.card_failed.set_value("0")
        self.card_time.set_value("00:00:00")
        self.progress_bar.setValue(0)
        self.txt_log.clear()

        # Update controls
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.statusBar().showMessage(f"Crawl läuft: {url}")

        # Start timer
        self.start_timestamp = time.time()
        self.timer.start(1000)

        # Setup Thread and Worker
        self.thread = QThread()
        self.worker = CrawlWorker(config)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.signal_page_discovered.connect(self._on_page_discovered)
        self.worker.signal_page_processed.connect(self._on_page_processed)
        self.worker.signal_page_failed.connect(self._on_page_failed)
        self.worker.signal_log.connect(self._append_log)
        self.worker.signal_finished.connect(self._on_crawl_finished)
        self.worker.signal_error.connect(self._on_crawl_error)

        self.worker.signal_finished.connect(self.thread.quit)
        self.worker.signal_error.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def stop_crawl(self) -> None:
        """Signals the worker to stop gracefully."""
        if self.worker:
            self.btn_stop.setEnabled(False)
            self.statusBar().showMessage("Breche Crawl ab...")
            self.worker.stop()

    def _on_page_discovered(self, url: str, title: str) -> None:
        self.total_discovered_pages += 1
        limit = (
            self.spn_max_pages.value()
            if self.chk_limit_pages.isChecked()
            else self.total_discovered_pages
        )
        if limit > 0:
            pct = int((self.processed_pages_count / limit) * 100)
            self.progress_bar.setValue(min(pct, 100))

    def _on_page_processed(self, url: str, title: str, local_path: str) -> None:
        self.processed_pages_count += 1
        self.card_pages.set_value(str(self.processed_pages_count))

        # Check images count from worker engine if available
        if self.worker and self.worker.engine:
            stats = self.worker.engine.state_manager.get_stats()
            self.images_count = stats.get("total_images", 0)
            self.card_images.set_value(str(self.images_count))

        limit = (
            self.spn_max_pages.value()
            if self.chk_limit_pages.isChecked()
            else max(self.total_discovered_pages, self.processed_pages_count)
        )
        if limit > 0:
            pct = int((self.processed_pages_count / limit) * 100)
            self.progress_bar.setValue(min(pct, 100))

        self.statusBar().showMessage(f"Verarbeitet: {title[:40]}")

    def _on_page_failed(self, url: str, title: str, error: str) -> None:
        self.failed_count += 1
        self.card_failed.set_value(str(self.failed_count))

    def _append_log(self, message: str, level: str) -> None:
        color_map = {
            "info": "#94a3b8",
            "success": "#4ade80",
            "warning": "#fbbf24",
            "error": "#f87171",
        }
        color = color_map.get(level, "#e2e8f0")
        current_time = time.strftime("%H:%M:%S")
        self.txt_log.appendHtml(
            f"<span style='color:#64748b;'>[{current_time}]</span> "
            f"<span style='color:{color};'>{message}</span>"
        )
        self.txt_log.moveCursor(QTextCursor.MoveOperation.End)

    def _on_crawl_finished(self, stats: dict) -> None:
        self.timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setValue(100)

        done_pages = stats.get("done_pages", self.processed_pages_count)
        total_images = stats.get("total_images", self.images_count)
        failed_pages = stats.get("failed_pages", self.failed_count)

        self.card_pages.set_value(str(done_pages))
        self.card_images.set_value(str(total_images))
        self.card_failed.set_value(str(failed_pages))

        self.statusBar().showMessage(
            f"Export erfolgreich abgeschlossen! ({done_pages} Seiten, {total_images} Bilder)"
        )
        self._append_log("✔ Crawl und Konvertierung erfolgreich abgeschlossen!", "success")

        QMessageBox.information(
            self,
            "Export abgeschlossen",
            f"Der Wiki-Export wurde erfolgreich abgeschlossen!\n\n"
            f"• Exportierte Artikel: {done_pages}\n"
            f"• Gespeicherte Grafiken: {total_images}\n"
            f"• Fehlgeschlagen: {failed_pages}\n\n"
            f"Zielordner: {self.txt_output_dir.text()}",
        )

    def _on_crawl_error(self, error_message: str) -> None:
        self.timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.statusBar().showMessage("Fehler beim Crawl-Vorgang!")
        QMessageBox.critical(
            self, "Fehler beim Export", f"Ein Fehler ist aufgetreten:\n{error_message}"
        )

    def _update_timer(self) -> None:
        if self.start_timestamp:
            elapsed_seconds = int(time.time() - self.start_timestamp)
            formatted_time = str(QTime(0, 0).addSecs(elapsed_seconds).toString("hh:mm:ss"))
            self.card_time.set_value(formatted_time)

    def _browse_output_dir(self) -> None:
        selected_dir = QFileDialog.getExistingDirectory(
            self, "Zielordner auswählen", self.txt_output_dir.text()
        )
        if selected_dir:
            self.txt_output_dir.setText(selected_dir)

    def _open_export_folder(self) -> None:
        folder_path = Path(self.txt_output_dir.text()).resolve()
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder_path)))

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "Über py-wiki-crawler",
            f"<b>py-wiki-crawler v{__version__}</b><br><br>"
            "Ein universelles Werkzeug zum rekursiven Herunterladen und Konvertieren von Wikis "
            "(MediaWiki/Fandom API sowie generische HTML-Wikis) in ein lokales Markdown-Archiv "
            "mit vollauflösenden Grafiken und relativer Querverlinkung.<br><br>"
            "<b>Tastaturkürzel:</b><br>"
            "• <b>F11:</b> Vollbildmodus umschalten<br>"
            "• <b>Esc:</b> Fenstermodus wiederherstellen<br>"
            "• <b>Strg+Q:</b> Beenden",
        )
