from unittest.mock import Mock, patch

from app.models import AlertDef
from app.services.message_processor import process


def _bug_alert():
    return AlertDef(name="Possível BUG geral", required=[], any=["bug"], exclude=[],
                     bug_mode=True, min_score=0, send_to_telegram=True)


def test_duplicate_with_same_price_does_not_add_history_point(db_conn):
    fake_response = Mock(status_code=200, url="https://loja.com/produto-x")
    with patch("app.parser.link_resolver.requests.head", return_value=fake_response):
        first = process(
            db_conn, telegram_message_id=1, chat_id=100, chat_title="Grupo A", sender_id=None,
            message_text="BUG: Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90 https://loja.com/produto-x",
            message_date="2026-07-01T10:00:00", alerts=[_bug_alert()],
        )
        second = process(
            db_conn, telegram_message_id=2, chat_id=200, chat_title="Grupo B", sender_id=None,
            message_text="BUG: Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90 https://loja.com/produto-x",
            message_date="2026-07-01T10:05:00", alerts=[_bug_alert()],
        )

    assert second.status == "DUPLICATE"
    count = db_conn.execute(
        "SELECT COUNT(*) FROM product_price_history WHERE product_id = ?", (first.product_id,)
    ).fetchone()[0]
    assert count == 1  # só o registro inicial da primeira mensagem


def test_duplicate_with_different_price_updates_promotion_and_adds_history_point(db_conn):
    fake_response = Mock(status_code=200, url="https://loja.com/produto-y")
    with patch("app.parser.link_resolver.requests.head", return_value=fake_response):
        first = process(
            db_conn, telegram_message_id=1, chat_id=100, chat_title="Grupo A", sender_id=None,
            message_text="BUG: Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90 https://loja.com/produto-y",
            message_date="2026-07-01T10:00:00", alerts=[_bug_alert()],
        )
        second = process(
            db_conn, telegram_message_id=2, chat_id=200, chat_title="Grupo B", sender_id=None,
            message_text="BUG: Motorola Moto G56 5G 256GB 8GB RAM por R$ 999,90 https://loja.com/produto-y",
            message_date="2026-07-01T12:00:00", alerts=[_bug_alert()],
        )

    assert second.status == "DUPLICATE"
    assert second.product_id == first.product_id

    promo_row = db_conn.execute(
        "SELECT price FROM promotions WHERE id = ?", (first.promotion_id,)
    ).fetchone()
    assert promo_row["price"] == 999.90

    count = db_conn.execute(
        "SELECT COUNT(*) FROM product_price_history WHERE product_id = ?", (first.product_id,)
    ).fetchone()[0]
    assert count == 2  # preço inicial + a atualização
