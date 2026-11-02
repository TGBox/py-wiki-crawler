from pathlib import Path

from py_wiki_crawler.converters.markdown import MarkdownConverter


def test_markdown_conversion_and_link_rewriting(tmp_path):
    converter = MarkdownConverter(base_url="https://game.fandom.com", output_dir=tmp_path)

    sample_html = """
    <div class="mw-parser-output">
        <div class="toc">Inhaltsverzeichnis</div>
        <p>Dies ist ein Schwert. Siehe <a href="/wiki/Shields/Hylian_Shield">Hylian Shield</a>.</p>
        <p>Externer Link: <a href="https://extern.com/info">Mehr Infos</a></p>
        <img src="https://static.wikia.nocookie.net/sword.png" alt="Sword Image" />
    </div>
    """

    current_md_path = tmp_path / "Weapons" / "Master_Sword.md"

    def mock_image_resolver(img_url: str) -> Path:
        return tmp_path / "assets" / "images" / "sword_abcdef12.png"

    md_output = converter.convert(
        title="Master Sword",
        html_content=sample_html,
        source_url="https://game.fandom.com/wiki/Master_Sword",
        current_md_path=current_md_path,
        image_resolver=mock_image_resolver,
    )

    # Verify YAML frontmatter
    assert "---" in md_output
    assert 'title: "Master Sword"' in md_output
    assert 'source_url: "https://game.fandom.com/wiki/Master_Sword"' in md_output

    # Verify title header
    assert "# Master Sword" in md_output

    # Verify TOC decomposed
    assert "Inhaltsverzeichnis" not in md_output

    # Verify internal link rewritten to relative .md path
    # from Weapons/Master_Sword.md to Shields/Hylian Shield.md -> ../Shields/Hylian Shield.md
    assert "[Hylian Shield](../Shields/Hylian Shield.md)" in md_output

    # Verify external link kept as-is
    assert "[Mehr Infos](https://extern.com/info)" in md_output

    # Verify image link rewritten to relative path:
    # Weapons/Master_Sword.md -> assets/images/sword_abcdef12.png
    assert "![Sword Image](../assets/images/sword_abcdef12.png)" in md_output


def test_lazy_loaded_fandom_images_use_data_src(tmp_path):
    converter = MarkdownConverter(base_url="https://game.fandom.com", output_dir=tmp_path)
    placeholder = (
        "data:image/gif;base64,R0lGODlhAQABAIABAAAAAP///yH5BAEAAAEALAAAAAABAAEAQAICTAEAOw=="
    )
    real_url = "https://static.wikia.nocookie.net/game/images/a/ab/Acid.png/revision/latest"
    sample_html = f"""
    <div class="mw-parser-output">
        <img src="{placeholder}" data-src="{real_url}" class="lazyload" alt="Acid" />
        <img src="{placeholder}" alt="Nur Platzhalter" />
    </div>
    """
    requested: list[str] = []

    def failing_resolver(img_url: str) -> None:
        requested.append(img_url)
        return None

    md_output = converter.convert(
        title="Acid",
        html_content=sample_html,
        source_url="https://game.fandom.com/wiki/Acid",
        current_md_path=tmp_path / "Acid.md",
        image_resolver=failing_resolver,
    )

    # Only the real URL is requested, never the base64 placeholder
    assert requested == [real_url]
    # Failed download falls back to the online URL instead of the placeholder
    assert real_url in md_output
    assert md_output.count("data:image") <= 1  # only the placeholder-only image keeps it
