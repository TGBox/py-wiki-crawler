import pytest

from py_wiki_crawler import __version__
from py_wiki_crawler.cli import main


def test_main_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        # Pass --version to main
        import sys

        sys_argv_backup = sys.argv
        sys.argv = ["py-wiki-crawler", "--version"]
        try:
            main()
        finally:
            sys.argv = sys_argv_backup

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out
