from pathlib import Path

from py_wiki_crawler.utils.path_utils import (
    get_relative_link,
    sanitize_path_segment,
    title_to_relative_path,
)


def test_sanitize_path_segment():
    assert sanitize_path_segment("Simple Name") == "Simple Name"
    assert sanitize_path_segment("File:With/Illegal*Chars?") == "File_With_Illegal_Chars_"
    assert sanitize_path_segment("Trailing Dot.") == "Trailing Dot"
    assert sanitize_path_segment("Trailing Space ") == "Trailing Space"
    assert sanitize_path_segment("CON") == "_CON"
    assert sanitize_path_segment("aux.txt") == "_aux.txt"
    assert sanitize_path_segment("") == "unbenannt"
    assert sanitize_path_segment("   ") == "unbenannt"


def test_title_to_relative_path():
    assert title_to_relative_path("Master Sword") == Path("Master Sword.md")
    assert title_to_relative_path("Items/Weapons/Swords/Excalibur") == Path(
        "Items", "Weapons", "Swords", "Excalibur.md"
    )
    assert title_to_relative_path("") == Path("index.md")


def test_get_relative_link():
    from_file = Path("output/Items/Weapons/Sword.md")
    to_image = Path("output/assets/images/sword_12345678.png")
    rel = get_relative_link(from_file, to_image)
    assert rel == "../../assets/images/sword_12345678.png"

    from_root_file = Path("output/index.md")
    rel_root = get_relative_link(from_root_file, to_image)
    assert rel_root == "assets/images/sword_12345678.png"
