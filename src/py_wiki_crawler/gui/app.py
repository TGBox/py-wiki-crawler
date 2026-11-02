"""
GUI application startup module.
"""

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from py_wiki_crawler.gui.main_window import MainWindow


def run_gui() -> int:
    """Initializes and runs the PySide6 Qt application."""
    # Enable high DPI scaling
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("py-wiki-crawler")
    app.setApplicationDisplayName("py-wiki-crawler")

    # Set clean default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    return app.exec()


def main() -> None:
    """Entry point for GUI CLI script."""
    sys.exit(run_gui())


if __name__ == "__main__":
    main()
