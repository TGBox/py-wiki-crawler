from src.main import main


def test_main(capsys):
    main()
    captured = capsys.readouterr()
    assert "py-wiki-crawler" in captured.out