from py_wiki_crawler.cli import build_parser


def test_cli_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["https://game.fandom.com"])
    assert args.url == "https://game.fandom.com"
    assert args.output == "wiki_export"
    assert args.delay == 0.4
    assert args.no_images is False
    assert args.force is False


def test_cli_parser_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "https://game.fandom.com",
            "-o",
            "custom_dir",
            "-d",
            "1.0",
            "-m",
            "50",
            "--max-depth",
            "3",
            "--no-images",
            "--force",
        ]
    )
    assert args.output == "custom_dir"
    assert args.delay == 1.0
    assert args.max_pages == 50
    assert args.max_depth == 3
    assert args.no_images is True
    assert args.force is True
