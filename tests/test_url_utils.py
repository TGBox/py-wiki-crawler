from py_wiki_crawler.utils.url_utils import (
    clean_image_url,
    extract_wiki_title_from_url,
    is_crawlable_article_url,
    is_same_domain,
    normalize_url,
)


def test_normalize_url():
    assert normalize_url("https://example.com/wiki/Test#section") == "https://example.com/wiki/Test"
    assert normalize_url("https://example.com/wiki/Test/") == "https://example.com/wiki/Test"


def test_is_same_domain():
    assert is_same_domain(
        "https://genshin.fandom.com/wiki/Main", "https://genshin.fandom.com/wiki/Sword"
    )
    assert not is_same_domain(
        "https://genshin.fandom.com/wiki/Main", "https://other.fandom.com/wiki/Sword"
    )
    assert not is_same_domain("https://genshin.fandom.com", "https://google.com")


def test_extract_wiki_title_from_url():
    assert extract_wiki_title_from_url("https://example.com/wiki/Master_Sword") == "Master Sword"
    assert (
        extract_wiki_title_from_url("https://example.com/wiki/Items/Weapon/Sword")
        == "Items/Weapon/Sword"
    )
    assert (
        extract_wiki_title_from_url("https://example.com/index.php?title=Shield_Item")
        == "Shield Item"
    )


def test_clean_image_url():
    # Fandom scale-down URL
    fandom_url = (
        "https://static.wikia.nocookie.net/gensin/images/5/5a/Sword.png/revision/latest"
        "/scale-to-width-down/350?cb=20210101"
    )
    cleaned_fandom = clean_image_url(fandom_url)
    assert cleaned_fandom == "https://static.wikia.nocookie.net/gensin/images/5/5a/Sword.png"

    # MediaWiki standard thumb URL
    mediawiki_thumb = "https://wiki.example.org/images/thumb/a/ab/Icon.png/120px-Icon.png"
    cleaned_mw = clean_image_url(mediawiki_thumb)
    assert cleaned_mw == "https://wiki.example.org/images/a/ab/Icon.png"


def test_is_crawlable_article_url():
    base = "https://mywiki.fandom.com"
    assert is_crawlable_article_url("https://mywiki.fandom.com/wiki/Hero", base)
    assert not is_crawlable_article_url("https://mywiki.fandom.com/wiki/Hero?action=edit", base)
    assert not is_crawlable_article_url(
        "https://mywiki.fandom.com/wiki/Special:RecentChanges", base
    )
    assert not is_crawlable_article_url("https://mywiki.fandom.com/wiki/File:Picture.png", base)
    assert not is_crawlable_article_url("https://other.com/wiki/Hero", base)
