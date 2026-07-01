from app.database import (
    find_promotion_by_dedupe_key,
    insert_occurrence,
    insert_promotion,
    insert_raw_message,
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
