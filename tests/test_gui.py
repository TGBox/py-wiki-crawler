import os

import pytest
from PySide6.QtWidgets import QApplication

# Set offscreen platform for headless test execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qapp():
    """Provides a QApplication instance for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_creation_and_fullscreen_toggle(qapp):
    from py_wiki_crawler.gui.main_window import MainWindow

    window = MainWindow()
    assert window is not None

    # Check initial windowed state
    assert window.isFullScreen() is False
    assert "Vollbildmodus (F11)" in window.btn_toggle_fullscreen.text()

    # Test toggling to fullscreen mode
    window.set_fullscreen_mode()
    assert window.isFullScreen() is True
    assert "Fenstermodus" in window.btn_toggle_fullscreen.text()

    # Test toggling back to windowed mode
    window.set_windowed_mode()
    assert window.isFullScreen() is False
    assert "Vollbildmodus" in window.btn_toggle_fullscreen.text()

    # Test toggle_fullscreen helper
    window.toggle_fullscreen()
    assert window.isFullScreen() is True
    window.toggle_fullscreen()
    assert window.isFullScreen() is False

    # Check essential UI controls
    assert window.txt_url is not None
    assert window.txt_output_dir is not None
    assert window.btn_start.isEnabled() is True
    assert window.btn_stop.isEnabled() is False
    assert window.progress_bar.value() == 0

    # Metric Cards
    window.card_pages.set_value("42")
    assert window.card_pages.lbl_value.text() == "42"

    window.close()
    window.deleteLater()
    qapp.processEvents()
