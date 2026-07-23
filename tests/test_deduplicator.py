from decimal import Decimal

from app.database import insert_promotion, insert_raw_message
from app.parser.link_resolver import LinkResult, LinkStatus
from app.rules.deduplicator import compute_dedupe_key, find_existing_promotion_id


def test_dedupe_key_uses_clean_url_first():
    link_result = LinkResult(url="https://loja.com/produto", status=LinkStatus.CLEANED)
    key = compute_dedupe_key(link_result, title="Produto X", price=Decimal("100"))
    assert key == "clean:https://loja.com/produto"


def test_dedupe_key_uses_resolved_url_when_no_clean():
    link_result = LinkResult(url="https://loja.com/produto", status=LinkStatus.RESOLVED)
    key = compute_dedupe_key(link_result, title="Produto X", price=Decimal("100"))
    assert key == "resolved:https://loja.com/produto"


def test_dedupe_key_uses_domain_path_on_error_resolving():
    link_result = LinkResult(url="https://loja.com/produto/123", status=LinkStatus.ERROR_RESOLVING)
    key = compute_dedupe_key(link_result, title="Produto X", price=Decimal("100"))
    assert key == "domain:loja.com/produto/123"


def test_dedupe_key_falls_back_to_title_and_price_when_no_link():
    link_result = LinkResult(url="", status=LinkStatus.NO_LINK)
    key = compute_dedupe_key(link_result, title="Notebook Lenovo", price=Decimal("2999.00"))
    assert key.startswith("title:")
    assert "2999.00" in key


def test_dedupe_key_no_title_no_link_uses_price_only():
    link_result = LinkResult(url="", status=LinkStatus.NO_LINK)
    key = compute_dedupe_key(link_result, title=None, price=Decimal("50"))
    assert key == "notitle:50"


def test_find_existing_promotion_id_returns_none_when_absent(db_conn):
    assert find_existing_promotion_id(db_conn, "clean:https://x.com/y") is None


def test_find_existing_promotion_id_returns_id_when_present(db_conn):
    raw_id = insert_raw_message(
        db_conn, telegram_message_id=1, chat_id=1, chat_title="Grupo",
        sender_id=None, message_text="texto", message_date="2026-07-01T10:00:00",
    )
    promo_id = insert_promotion(db_conn, raw_message_id=raw_id, dedupe_key="clean:https://x.com/y")
    found = find_existing_promotion_id(db_conn, "clean:https://x.com/y")
    assert found == promo_id
