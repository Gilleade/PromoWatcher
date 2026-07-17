import sqlite3

import pytest

from app.database import (
    insert_favorite,
    insert_price_history_point,
    insert_product,
    insert_product_image,
    insert_promotion,
    insert_raw_message,
    upsert_product_alert,
)
from app.products.product_service import merge_products


def _product(conn, title, key, **kwargs):
    return insert_product(
        conn,
        canonical_title=title,
        variant_key=key,
        **kwargs,
    )


def test_merge_moves_all_product_relations_and_recomputes_summary(db_conn):
    target_id = _product(db_conn, "Produto correto", "target|1")
    source_id = _product(
        db_conn, "Produto duplicado", "source|1", image_url="/media/source.jpg",
    )
    insert_favorite(db_conn, source_id)
    target_alert_id = upsert_product_alert(
        db_conn, product_id=target_id, enabled=False,
        max_price=500.0, send_to_telegram=False,
    )
    upsert_product_alert(
        db_conn, product_id=source_id, enabled=True,
        max_price=700.0, send_to_telegram=True,
    )
    db_conn.execute(
        """
        INSERT INTO product_specs (product_id, spec_key, spec_value)
        VALUES (?, 'cor', 'preto'), (?, 'cor', 'azul'), (?, 'armazenamento', '256GB')
        """,
        (target_id, source_id, source_id),
    )
    db_conn.commit()
    insert_product_image(
        db_conn, product_id=source_id,
        image_url="/media/source.jpg", local_path="data/images/source.jpg",
        is_primary=True,
    )

    raw_target = insert_raw_message(
        db_conn, telegram_message_id=1, chat_id=1, chat_title="Grupo",
        sender_id=None, message_text="target", message_date="2026-07-16T10:00:00",
    )
    promo_target = insert_promotion(
        db_conn, raw_message_id=raw_target, price=900.0, status="APPROVED",
    )
    db_conn.execute(
        "UPDATE promotions SET product_id = ? WHERE id = ?", (target_id, promo_target)
    )
    db_conn.commit()
    insert_price_history_point(
        db_conn, product_id=target_id, promotion_id=promo_target, price=900.0,
    )

    raw_source = insert_raw_message(
        db_conn, telegram_message_id=2, chat_id=1, chat_title="Grupo",
        sender_id=None, message_text="source", message_date="2026-07-16T11:00:00",
    )
    promo_source = insert_promotion(
        db_conn, raw_message_id=raw_source, price=800.0, status="APPROVED",
        installment_count=10, installment_price=80.0, installment_no_interest=True,
    )
    db_conn.execute(
        "UPDATE promotions SET product_id = ? WHERE id = ?", (source_id, promo_source)
    )
    db_conn.commit()
    insert_price_history_point(
        db_conn, product_id=source_id, promotion_id=promo_source, price=800.0,
    )

    merge_products(
        db_conn,
        source_product_id=source_id,
        target_product_id=target_id,
        reason="duplicado confirmado",
    )

    source = db_conn.execute(
        "SELECT * FROM products WHERE id = ?", (source_id,)
    ).fetchone()
    target = db_conn.execute(
        "SELECT * FROM products WHERE id = ?", (target_id,)
    ).fetchone()
    assert source["status"] == "MERGED"
    assert source["merged_into_product_id"] == target_id
    assert target["image_url"] == "/media/source.jpg"
    assert target["lowest_price_ever"] == 800.0
    assert target["last_price"] == 800.0
    assert target["last_installment_count"] == 10
    assert target["last_installment_price"] == 80.0

    assert db_conn.execute(
        "SELECT COUNT(*) FROM favorites WHERE product_id = ?", (target_id,)
    ).fetchone()[0] == 1
    alert = db_conn.execute(
        "SELECT * FROM product_alerts WHERE product_id = ?", (target_id,)
    ).fetchone()
    assert alert["id"] == target_alert_id
    assert alert["enabled"] == 1
    assert alert["max_price"] == 700.0
    assert alert["send_to_telegram"] == 1
    assert db_conn.execute(
        "SELECT COUNT(*) FROM product_alerts WHERE product_id = ?", (source_id,)
    ).fetchone()[0] == 0

    specs = {
        row["spec_key"]: row["spec_value"]
        for row in db_conn.execute(
            "SELECT * FROM product_specs WHERE product_id = ?", (target_id,)
        ).fetchall()
    }
    assert specs == {"cor": "preto", "armazenamento": "256GB"}
    assert db_conn.execute(
        "SELECT COUNT(*) FROM product_specs WHERE product_id = ?", (source_id,)
    ).fetchone()[0] == 0
    assert db_conn.execute(
        "SELECT COUNT(*) FROM product_images WHERE product_id = ?", (target_id,)
    ).fetchone()[0] == 1
    assert db_conn.execute(
        "SELECT COUNT(*) FROM promotions WHERE product_id = ?", (target_id,)
    ).fetchone()[0] == 2
    assert db_conn.execute(
        "SELECT COUNT(*) FROM product_price_history WHERE product_id = ?", (target_id,)
    ).fetchone()[0] == 2

    merge = db_conn.execute("SELECT * FROM product_merges").fetchone()
    assert merge["source_product_id"] == source_id
    assert merge["target_product_id"] == target_id
    assert merge["reason"] == "duplicado confirmado"


def test_merge_rolls_back_every_change_when_any_step_fails(db_conn):
    target_id = _product(db_conn, "Destino", "target|rollback")
    source_id = _product(db_conn, "Origem", "source|rollback")
    insert_favorite(db_conn, source_id)
    raw_id = insert_raw_message(
        db_conn, telegram_message_id=1, chat_id=1, chat_title="Grupo",
        sender_id=None, message_text="source", message_date="2026-07-16T10:00:00",
    )
    promotion_id = insert_promotion(
        db_conn, raw_message_id=raw_id, price=100.0, status="APPROVED",
    )
    db_conn.execute(
        "UPDATE promotions SET product_id = ? WHERE id = ?", (source_id, promotion_id)
    )
    db_conn.commit()
    insert_price_history_point(
        db_conn, product_id=source_id, promotion_id=promotion_id, price=100.0,
    )
    db_conn.execute(
        """
        CREATE TRIGGER fail_product_history_merge
        BEFORE UPDATE OF product_id ON product_price_history
        BEGIN
            SELECT RAISE(ABORT, 'falha simulada');
        END
        """
    )
    db_conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="falha simulada"):
        merge_products(
            db_conn,
            source_product_id=source_id,
            target_product_id=target_id,
        )

    assert db_conn.execute(
        "SELECT status FROM products WHERE id = ?", (source_id,)
    ).fetchone()["status"] == "ACTIVE"
    assert db_conn.execute(
        "SELECT product_id FROM promotions WHERE id = ?", (promotion_id,)
    ).fetchone()["product_id"] == source_id
    assert db_conn.execute(
        "SELECT product_id FROM product_price_history"
    ).fetchone()["product_id"] == source_id
    assert db_conn.execute(
        "SELECT COUNT(*) FROM favorites WHERE product_id = ?", (source_id,)
    ).fetchone()[0] == 1
    assert db_conn.execute("SELECT COUNT(*) FROM product_merges").fetchone()[0] == 0
