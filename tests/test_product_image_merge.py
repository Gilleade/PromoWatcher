from app.database import insert_product, insert_raw_message
from app.products.product_service import attach_product_image, merge_products
from app.services.product_image_worker import enqueue_image_candidate


def _product(conn, title, key):
    return insert_product(conn, canonical_title=title, variant_key=key)


def _raw(conn, message_id):
    return insert_raw_message(
        conn,
        telegram_message_id=message_id,
        chat_id=100,
        chat_title="Canal",
        sender_id=None,
        message_text="Produto",
        message_date="2026-07-17T10:00:00",
    )


def test_merge_preserves_target_when_both_products_have_image(db_conn):
    target_id = _product(db_conn, "Destino", "destino|1")
    source_id = _product(db_conn, "Origem", "origem|1")
    attach_product_image(db_conn, product_id=target_id, local_path="data/images/target.jpg")
    attach_product_image(db_conn, product_id=source_id, local_path="data/images/source.jpg")

    merge_products(
        db_conn, source_product_id=source_id, target_product_id=target_id,
    )

    target = db_conn.execute(
        "SELECT image_url FROM products WHERE id = ?", (target_id,)
    ).fetchone()
    assert target["image_url"] == "/media/target.jpg"
    assert db_conn.execute(
        "SELECT COUNT(*) FROM product_images WHERE product_id = ?", (target_id,)
    ).fetchone()[0] == 1
    assert db_conn.execute(
        "SELECT COUNT(*) FROM product_images WHERE product_id = ?", (source_id,)
    ).fetchone()[0] == 0


def test_merge_combines_pending_image_candidates(db_conn):
    target_id = _product(db_conn, "Destino", "destino|1")
    source_id = _product(db_conn, "Origem", "origem|1")
    target_raw = _raw(db_conn, 1)
    source_raw = _raw(db_conn, 2)
    enqueue_image_candidate(
        db_conn, product_id=target_id, raw_message_id=target_raw,
    )
    enqueue_image_candidate(
        db_conn, product_id=source_id, raw_message_id=source_raw,
    )

    merge_products(
        db_conn, source_product_id=source_id, target_product_id=target_id,
    )

    assert db_conn.execute(
        "SELECT COUNT(*) FROM product_image_jobs WHERE product_id = ?", (target_id,)
    ).fetchone()[0] == 1
    assert db_conn.execute(
        "SELECT COUNT(*) FROM product_image_jobs WHERE product_id = ?", (source_id,)
    ).fetchone()[0] == 0
    assert db_conn.execute(
        "SELECT COUNT(*) FROM product_image_candidates WHERE product_id = ?", (target_id,)
    ).fetchone()[0] == 2
