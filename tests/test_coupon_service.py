from app.database import insert_raw_message
from app.parser.link_resolver import LinkResult, LinkStatus
from app.parser.text_parser import parse_message
from app.services.coupon_service import compute_coupon_dedupe_key, process_coupon_message


def _no_link_result():
    return LinkResult(url="", status=LinkStatus.NO_LINK, store_domain=None)


def test_dedupe_key_prefers_code_and_store():
    key = compute_coupon_dedupe_key(code="BUG10", store_domain="loja.com", url=None, discount_label=None)
    assert key == "code:loja.com:BUG10"


def test_dedupe_key_falls_back_to_url_without_code():
    key = compute_coupon_dedupe_key(code=None, store_domain=None, url="https://loja.com/cupom", discount_label=None)
    assert key == "url:https://loja.com/cupom"


def test_dedupe_key_falls_back_to_label_and_store():
    key = compute_coupon_dedupe_key(code=None, store_domain="mercadolivre.com.br", url=None, discount_label="30% OFF")
    assert key == "label:mercadolivre.com.br:30% OFF"


def test_dedupe_key_generic_fallback():
    key = compute_coupon_dedupe_key(code=None, store_domain=None, url=None, discount_label=None)
    assert key == "label:GENERIC"


def test_process_coupon_message_creates_new_coupon(db_conn):
    parsed = parse_message("Cupom BUG10 dá 10% de desconto na loja, sem produto especifico")
    raw_id = insert_raw_message(
        db_conn, telegram_message_id=1, chat_id=1, chat_title="Grupo", sender_id=None,
        message_text=parsed.raw_text, message_date="2026-07-16T10:00:00",
    )

    result = process_coupon_message(
        db_conn, raw_message_id=raw_id, parsed=parsed, link_result=_no_link_result(), chat_title="Grupo",
    )

    assert result.status == "NEW_COUPON"
    row = db_conn.execute("SELECT * FROM coupons_standalone WHERE id = ?", (result.coupon_id,)).fetchone()
    assert row["code"] == "BUG10"
    assert row["repeat_count"] == 0


def test_process_coupon_message_second_occurrence_increments_repeat_count(db_conn):
    parsed = parse_message("Cupom BUG20 dá 20% de desconto na loja")
    raw_id_1 = insert_raw_message(
        db_conn, telegram_message_id=1, chat_id=1, chat_title="Grupo A", sender_id=None,
        message_text=parsed.raw_text, message_date="2026-07-16T10:00:00",
    )
    first = process_coupon_message(
        db_conn, raw_message_id=raw_id_1, parsed=parsed, link_result=_no_link_result(), chat_title="Grupo A",
    )

    raw_id_2 = insert_raw_message(
        db_conn, telegram_message_id=2, chat_id=2, chat_title="Grupo B", sender_id=None,
        message_text=parsed.raw_text, message_date="2026-07-16T11:00:00",
    )
    second = process_coupon_message(
        db_conn, raw_message_id=raw_id_2, parsed=parsed, link_result=_no_link_result(), chat_title="Grupo B",
    )

    assert second.status == "DUPLICATE_COUPON"
    assert second.coupon_id == first.coupon_id
    row = db_conn.execute("SELECT repeat_count FROM coupons_standalone WHERE id = ?", (first.coupon_id,)).fetchone()
    assert row["repeat_count"] == 1
