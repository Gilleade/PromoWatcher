from unittest.mock import patch

from app.models import AlertDef
from app.services.message_processor import process


def _bug_alert():
    return AlertDef(name="Possível BUG geral", required=[], any=["bug"], exclude=[],
                     bug_mode=True, min_score=0, send_to_telegram=True)


def test_coupon_only_message_does_not_create_promotion(db_conn):
    with patch("app.parser.link_resolver.requests.head", side_effect=ConnectionError):
        result = process(
            db_conn, telegram_message_id=1, chat_id=100, chat_title="Grupo A", sender_id=None,
            message_text="Cupom Mercado Livre - 30% OFF em compras acima de 69 em produtos Elseve",
            message_date="2026-07-16T10:00:00", alerts=[_bug_alert()],
        )

    assert result.status == "NEW_COUPON"
    assert result.promotion_id is None
    assert result.coupon_id is not None

    promo_count = db_conn.execute("SELECT COUNT(*) FROM promotions").fetchone()[0]
    assert promo_count == 0
    coupon_count = db_conn.execute("SELECT COUNT(*) FROM coupons_standalone").fetchone()[0]
    assert coupon_count == 1


def test_product_message_with_price_still_creates_promotion(db_conn):
    with patch("app.parser.link_resolver.requests.head", side_effect=ConnectionError):
        result = process(
            db_conn, telegram_message_id=1, chat_id=100, chat_title="Grupo A", sender_id=None,
            message_text="BUG: Notebook por R$ 500,00 com cupom NOTE50",
            message_date="2026-07-16T10:00:00", alerts=[_bug_alert()],
        )

    assert result.status == "NEW_APPROVED"
    assert result.promotion_id is not None
    coupon_count = db_conn.execute("SELECT COUNT(*) FROM coupons_standalone").fetchone()[0]
    assert coupon_count == 0
