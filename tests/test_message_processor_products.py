from unittest.mock import Mock, patch

from app.models import AlertDef
from app.services.message_processor import process


def _bug_alert():
    return AlertDef(name="Possível BUG geral", required=[], any=["bug"], exclude=[],
                     bug_mode=True, min_score=0, send_to_telegram=True)


def _promotion_row(conn, promotion_id):
    return conn.execute("SELECT * FROM promotions WHERE id = ?", (promotion_id,)).fetchone()


def test_new_identifiable_product_creates_product_and_links_promotion(db_conn):
    with patch("app.parser.link_resolver.requests.head", side_effect=ConnectionError):
        result = process(
            db_conn,
            telegram_message_id=1,
            chat_id=100,
            chat_title="Grupo A",
            sender_id=None,
            message_text="BUG: Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90",
            message_date="2026-07-01T10:00:00",
            alerts=[_bug_alert()],
        )

    row = _promotion_row(db_conn, result.promotion_id)
    assert row["product_match_status"] == "AUTO_NEW"
    assert row["product_id"] is not None

    product = db_conn.execute(
        "SELECT * FROM products WHERE id = ?", (row["product_id"],)
    ).fetchone()
    assert product["brand"] == "motorola"
    assert product["storage_gb"] == 256


def test_repeated_product_from_different_group_auto_matches(db_conn):
    with patch("app.parser.link_resolver.requests.head", side_effect=ConnectionError):
        first = process(
            db_conn,
            telegram_message_id=1,
            chat_id=100,
            chat_title="Grupo A",
            sender_id=None,
            message_text="BUG: Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90 na Amazon",
            message_date="2026-07-01T10:00:00",
            alerts=[_bug_alert()],
        )
        second = process(
            db_conn,
            telegram_message_id=2,
            chat_id=200,
            chat_title="Grupo B",
            sender_id=None,
            message_text="BUG: MOTOROLA MOTO G56 5G 256GB 8GB RAM por R$ 1.093,90 - CUPOM no Magalu",
            message_date="2026-07-01T11:00:00",
            alerts=[_bug_alert()],
        )

    row_first = _promotion_row(db_conn, first.promotion_id)
    row_second = _promotion_row(db_conn, second.promotion_id)

    assert row_first["product_match_status"] == "AUTO_NEW"
    assert row_second["product_match_status"] == "AUTO_MATCH"
    assert row_second["product_id"] == row_first["product_id"]

    count = db_conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    assert count == 1


def test_unidentifiable_product_goes_to_review_queue(db_conn):
    with patch("app.parser.link_resolver.requests.head", side_effect=ConnectionError):
        result = process(
            db_conn,
            telegram_message_id=1,
            chat_id=100,
            chat_title="Grupo A",
            sender_id=None,
            message_text="BUG imperdível por R$ 199,90, corre que acaba!",
            message_date="2026-07-01T10:00:00",
            alerts=[_bug_alert()],
        )

    row = _promotion_row(db_conn, result.promotion_id)
    assert row["product_match_status"] == "NEEDS_REVIEW"
    assert row["product_id"] is None

    queue_row = db_conn.execute(
        "SELECT * FROM product_match_queue WHERE promotion_id = ?", (result.promotion_id,)
    ).fetchone()
    assert queue_row is not None
    assert queue_row["status"] == "PENDING"


def test_message_without_price_skips_product_matching(db_conn):
    with patch("app.parser.link_resolver.requests.head", side_effect=ConnectionError):
        result = process(
            db_conn,
            telegram_message_id=1,
            chat_id=100,
            chat_title="Grupo A",
            sender_id=None,
            message_text="BUG detectado, sem preço divulgado ainda",
            message_date="2026-07-01T10:00:00",
            alerts=[_bug_alert()],
        )

    row = _promotion_row(db_conn, result.promotion_id)
    assert row["product_match_status"] == "UNMATCHED"
    assert row["product_id"] is None

    count = db_conn.execute("SELECT COUNT(*) FROM product_match_queue").fetchone()[0]
    assert count == 0
