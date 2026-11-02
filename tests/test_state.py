from py_wiki_crawler.core.state import StateManager


def test_state_manager_lifecycle(tmp_path):
    db_file = tmp_path / ".crawler_state.db"
    manager = StateManager(db_file)

    # Adding pages
    added = manager.add_page("https://wiki.org/wiki/Page1", "Page 1", depth=0)
    assert added is True

    # Re-adding same page should be ignored
    added_again = manager.add_page("https://wiki.org/wiki/Page1", "Page 1", depth=0)
    assert added_again is False

    # Check pending
    pending = manager.get_pending_pages()
    assert len(pending) == 1
    assert pending[0]["url"] == "https://wiki.org/wiki/Page1"

    # Mark done
    manager.mark_page_done("https://wiki.org/wiki/Page1", "Page 1", "Page 1.md", http_status=200)
    assert manager.is_page_done("https://wiki.org/wiki/Page1") is True
    assert len(manager.get_pending_pages()) == 0

    # Image recording and deduplication
    manager.record_image(
        source_url="https://img.org/sword.png",
        sha256_hash="abcdef1234567890",
        local_path="assets/images/sword.png",
        size_bytes=1024,
    )
    img_record = manager.get_image_by_url("https://img.org/sword.png")
    assert img_record is not None
    assert img_record["sha256"] == "abcdef1234567890"

    hash_record = manager.get_image_by_hash("abcdef1234567890")
    assert hash_record is not None
    assert hash_record["local_path"] == "assets/images/sword.png"

    # Stats
    stats = manager.get_stats()
    assert stats["done_pages"] == 1
    assert stats["pending_pages"] == 0
    assert stats["total_images"] == 1


def test_requeue_failed_and_all_pages(tmp_path):
    manager = StateManager(tmp_path / ".crawler_state.db")
    manager.add_pages_bulk([("u1", "A", 0), ("u2", "B", 0), ("u3", "C", 0)])
    manager.mark_page_done("u1", "A", "A.md")
    manager.mark_page_failed("u2", "Kein Inhalt")

    assert manager.requeue_failed_pages() == 1
    pending = {p["url"] for p in manager.get_pending_pages()}
    assert pending == {"u2", "u3"}

    assert manager.requeue_all_pages() == 3
    assert len(manager.get_pending_pages()) == 3
