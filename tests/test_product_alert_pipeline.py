from unittest.mock import Mock, patch

from app.database import (
    insert_notification,
    insert_product,
    update_product_status,
    upsert_product_alert,
)
from app.models import AlertDef
from app.parser.text_parser import parse_message
from app.products.spec_extractor import build_variant_key, extract_specs
from app.services.message_processor import process
from app.services.notification_service import build_notification_text


PRODUCT_TEXT = "Motorola Moto G56 5G 256GB 8GB RAM"


def _seed_matching_product(conn):
    specs = extract_specs(PRODUCT_TEXT)
    return insert_product(
        conn,
        canonical_title="Celular Motorola Moto G56 5G 256GB",
        variant_key=build_variant_key(
            specs.brand, specs.model, specs.storage_gb, specs.ram_gb,
        ),
        category=specs.category,
        brand=specs.brand,
        model=specs.model,
        storage_gb=specs.storage_gb,
        ram_gb=specs.ram_gb,
    )


def _process(conn, *, message_text, message_id=1, alerts=None):
    return process(
        conn,
        telegram_message_id=message_id,
        chat_id=100,
        chat_title="Grupo A",
        sender_id=None,
        message_text=message_text,
        message_date="2026-07-16T10:00:00",
        alerts=alerts or [],
    )


def test_product_alert_approves_and_notifies_without_global_alert(db_conn):
    product_id = _seed_matching_product(db_conn)
    product_alert_id = upsert_product_alert(
        db_conn, product_id=product_id, enabled=True,
        max_price=1000.0, send_to_telegram=True,
    )

    result = _process(db_conn, message_text=f"{PRODUCT_TEXT} por R$ 899,00")

    assert result.status == "NEW_APPROVED"
    assert result.notify is True
    assert result.matched_alert is None
    assert result.product_alert_id == product_alert_id
    assert result.product_alert_name == "Celular Motorola Moto G56 5G 256GB"
    promotion = db_conn.execute(
        "SELECT status FROM promotions WHERE id = ?", (result.promotion_id,)
    ).fetchone()
    assert promotion["status"] == "APPROVED"


def test_product_alert_respects_its_max_price(db_conn):
    product_id = _seed_matching_product(db_conn)
    upsert_product_alert(
        db_conn, product_id=product_id, enabled=True,
        max_price=800.0, send_to_telegram=True,
    )

    result = _process(db_conn, message_text=f"{PRODUCT_TEXT} por R$ 899,00")

    assert result.status == "NEW_IGNORED"
    assert result.notify is False
    assert result.product_alert_id is None


def test_global_alert_max_price_is_a_hard_limit(db_conn):
    alert = AlertDef(
        name="Notebook barato",
        required=["notebook"],
        max_price=1000.0,
        min_score=0,
    )

    result = _process(
        db_conn,
        message_text="Notebook Dell Inspiron por R$ 5.000,00",
        alerts=[alert],
    )

    assert result.status == "NEW_IGNORED"
    assert result.notify is False


def test_blocked_product_is_not_recreated_or_added_to_price_history(db_conn):
    product_id = _seed_matching_product(db_conn)
    update_product_status(db_conn, product_id, "BLOCKED")

    result = _process(db_conn, message_text=f"{PRODUCT_TEXT} por R$ 899,00")

    promotion = db_conn.execute(
        "SELECT product_id, product_match_status FROM promotions WHERE id = ?",
        (result.promotion_id,),
    ).fetchone()
    assert promotion["product_id"] == product_id
    assert promotion["product_match_status"] == "BLOCKED"
    assert db_conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
    assert db_conn.execute(
        "SELECT COUNT(*) FROM product_price_history"
    ).fetchone()[0] == 0


def test_price_update_triggers_product_alert_for_duplicate_link(db_conn):
    product_id = _seed_matching_product(db_conn)
    product_alert_id = upsert_product_alert(
        db_conn, product_id=product_id, enabled=True,
        max_price=1000.0, send_to_telegram=True,
    )
    fake_response = Mock(status_code=200, url="https://loja.com/produto")

    with patch("app.parser.link_resolver.requests.head", return_value=fake_response):
        first = _process(
            db_conn,
            message_text=f"{PRODUCT_TEXT} por R$ 900,00 https://loja.com/produto",
            message_id=1,
        )
        second = _process(
            db_conn,
            message_text=f"{PRODUCT_TEXT} por R$ 800,00 https://loja.com/produto",
            message_id=2,
        )

    assert first.status == "NEW_APPROVED"
    assert second.status == "PRICE_UPDATE_APPROVED"
    assert second.notify is True
    assert second.product_alert_id == product_alert_id
    prices = [
        row["price"]
        for row in db_conn.execute(
            "SELECT price FROM product_price_history ORDER BY id"
        ).fetchall()
    ]
    assert prices == [900.0, 800.0]


def test_product_alert_notification_is_identified_in_text_and_database(db_conn):
    product_id = _seed_matching_product(db_conn)
    product_alert_id = upsert_product_alert(
        db_conn, product_id=product_id, enabled=True,
        max_price=1000.0, send_to_telegram=True,
    )
    result = _process(db_conn, message_text=f"{PRODUCT_TEXT} por R$ 899,00")
    parsed = parse_message(f"{PRODUCT_TEXT} por R$ 899,00")
    message = build_notification_text(
        alert=None,
        alert_name=result.product_alert_name,
        title_guess=parsed.title_guess,
        price=float(parsed.price),
        coupon=None,
        link_status="NO_LINK",
        url=None,
        source_chat_title="Grupo A",
        score=None,
        repeat_count=0,
        reason=result.reason,
    )
    notification_id = insert_notification(
        db_conn,
        promotion_id=result.promotion_id,
        alert_id=None,
        product_alert_id=product_alert_id,
        channel="telegram",
        message_sent=message,
    )

    assert "Alerta: Celular Motorola Moto G56" in message
    assert "Score:" not in message
    notification = db_conn.execute(
        "SELECT * FROM notifications WHERE id = ?", (notification_id,)
    ).fetchone()
    assert notification["product_alert_id"] == product_alert_id
    assert notification["alert_id"] is None


def test_product_alert_can_enable_notification_when_global_alert_is_silent(db_conn):
    product_id = _seed_matching_product(db_conn)
    product_alert_id = upsert_product_alert(
        db_conn, product_id=product_id, enabled=True,
        max_price=1000.0, send_to_telegram=True,
    )
    global_alert = AlertDef(
        name="Motorola silencioso",
        required=["motorola"],
        min_score=0,
        send_to_telegram=False,
    )

    result = _process(
        db_conn,
        message_text=f"{PRODUCT_TEXT} por R$ 899,00",
        alerts=[global_alert],
    )

    assert result.status == "NEW_APPROVED"
    assert result.matched_alert is global_alert
    assert result.product_alert_id == product_alert_id
    assert result.notify is True
