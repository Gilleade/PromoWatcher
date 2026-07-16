from app.database import (
    find_promotion_by_dedupe_key,
    insert_occurrence,
    insert_product,
    insert_product_image,
    insert_promotion,
    insert_raw_message,
    update_product_image_url_if_null,
    upsert_alert,
)


def _upsert_bug_alert(conn, *, min_score=0):
    return upsert_alert(
        conn, name="Possível BUG geral", enabled=True, alert_type="BUG_RULE",
        required_terms="[]", optional_terms='["bug"]', excluded_terms="[]",
        min_price=None, max_price=None, min_discount_percent=0, bug_mode=True,
        min_score=min_score, send_to_telegram=True,
    )


def test_upsert_alert_creates_new_row(db_conn):
    alert_id = _upsert_bug_alert(db_conn)
    row = db_conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    assert row["name"] == "Possível BUG geral"
    assert row["bug_mode"] == 1


def test_upsert_alert_updates_existing_row_by_name(db_conn):
    first_id = _upsert_bug_alert(db_conn, min_score=0)
    second_id = _upsert_bug_alert(db_conn, min_score=50)

    assert first_id == second_id
    row = db_conn.execute("SELECT * FROM alerts WHERE id = ?", (first_id,)).fetchone()
    assert row["min_score"] == 50
    count = db_conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    assert count == 1


def test_init_db_creates_tables(db_conn):
    tables = {
        row["name"]
        for row in db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    expected = {
        "raw_messages",
        "promotions",
        "alerts",
        "promotion_occurrences",
        "notifications",
    }
    assert expected.issubset(tables)


def test_insert_and_read_raw_message(db_conn):
    raw_id = insert_raw_message(
        db_conn,
        telegram_message_id=123,
        chat_id=456,
        chat_title="Grupo Teste",
        sender_id=789,
        message_text="Bug: notebook R$ 2.000,00",
        message_date="2026-07-01T10:00:00",
    )
    row = db_conn.execute("SELECT * FROM raw_messages WHERE id = ?", (raw_id,)).fetchone()
    assert row["chat_title"] == "Grupo Teste"
    assert row["message_text"].startswith("Bug:")


def test_insert_promotion_and_find_by_dedupe_key(db_conn):
    raw_id = insert_raw_message(
        db_conn,
        telegram_message_id=1,
        chat_id=1,
        chat_title="Grupo A",
        sender_id=None,
        message_text="texto",
        message_date="2026-07-01T10:00:00",
    )
    promo_id = insert_promotion(
        db_conn,
        raw_message_id=raw_id,
        title_guess="Notebook X",
        dedupe_key="key-123",
        status="APPROVED",
        score=90,
    )
    found = find_promotion_by_dedupe_key(db_conn, "key-123")
    assert found is not None
    assert found["id"] == promo_id
    assert found["title_guess"] == "Notebook X"


def test_insert_occurrence_increments_repeat_count(db_conn):
    raw_id = insert_raw_message(
        db_conn,
        telegram_message_id=1,
        chat_id=1,
        chat_title="Grupo A",
        sender_id=None,
        message_text="texto",
        message_date="2026-07-01T10:00:00",
    )
    promo_id = insert_promotion(db_conn, raw_message_id=raw_id, dedupe_key="key-456")

    raw_id_2 = insert_raw_message(
        db_conn,
        telegram_message_id=2,
        chat_id=2,
        chat_title="Grupo B",
        sender_id=None,
        message_text="texto duplicado",
        message_date="2026-07-01T10:05:00",
    )
    insert_occurrence(
        db_conn,
        promotion_id=promo_id,
        raw_message_id=raw_id_2,
        chat_title="Grupo B",
        message_date="2026-07-01T10:05:00",
    )

    updated = db_conn.execute(
        "SELECT repeat_count FROM promotions WHERE id = ?", (promo_id,)
    ).fetchone()
    assert updated["repeat_count"] == 1


def _seed_product(conn):
    return insert_product(conn, canonical_title="Produto Teste", variant_key="teste|teste|1|1")


def test_insert_product_image(db_conn):
    product_id = _seed_product(db_conn)
    image_id = insert_product_image(
        db_conn, product_id=product_id, local_path="data/images/1_2_3.jpg",
        image_url="/media/1_2_3.jpg", is_primary=True,
    )
    row = db_conn.execute("SELECT * FROM product_images WHERE id = ?", (image_id,)).fetchone()
    assert row["product_id"] == product_id
    assert row["image_url"] == "/media/1_2_3.jpg"
    assert row["source"] == "TELEGRAM_MEDIA"
    assert row["is_primary"] == 1


def test_update_product_image_url_if_null_sets_when_empty(db_conn):
    product_id = _seed_product(db_conn)
    became_primary = update_product_image_url_if_null(db_conn, product_id, "/media/1_2_3.jpg")

    assert became_primary is True
    row = db_conn.execute("SELECT image_url FROM products WHERE id = ?", (product_id,)).fetchone()
    assert row["image_url"] == "/media/1_2_3.jpg"


def test_update_product_image_url_if_null_does_not_overwrite(db_conn):
    product_id = _seed_product(db_conn)
    update_product_image_url_if_null(db_conn, product_id, "/media/first.jpg")

    became_primary = update_product_image_url_if_null(db_conn, product_id, "/media/second.jpg")

    assert became_primary is False
    row = db_conn.execute("SELECT image_url FROM products WHERE id = ?", (product_id,)).fetchone()
    assert row["image_url"] == "/media/first.jpg"
