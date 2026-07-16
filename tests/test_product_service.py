from app.products.matcher import DECISION_AUTO_MATCH, DECISION_AUTO_NEW, DECISION_NEEDS_REVIEW
from app.products.product_service import get_or_create_product
from app.products.spec_extractor import extract_specs


def test_get_or_create_creates_new_product_first_time(db_conn):
    specs = extract_specs("Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90")

    product_id, decision = get_or_create_product(db_conn, specs)

    assert product_id is not None
    assert decision.decision == DECISION_AUTO_NEW
    row = db_conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    assert row["brand"] == "motorola"
    assert row["storage_gb"] == 256


def test_second_post_of_same_product_reuses_id(db_conn):
    specs_a = extract_specs("Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90 no Magalu")
    product_id_a, decision_a = get_or_create_product(db_conn, specs_a)
    assert decision_a.decision == DECISION_AUTO_NEW

    specs_b = extract_specs("MOTOROLA MOTO G56 5G 256GB 8GB RAM - CUPOM DISPONIVEL na Amazon")
    product_id_b, decision_b = get_or_create_product(db_conn, specs_b)

    assert decision_b.decision == DECISION_AUTO_MATCH
    assert product_id_b == product_id_a


def test_different_storage_creates_separate_products(db_conn):
    specs_256 = extract_specs("Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90")
    specs_128 = extract_specs("Motorola Moto G56 5G 128GB 8GB RAM por R$ 899,90")

    product_id_256, _ = get_or_create_product(db_conn, specs_256)
    product_id_128, _ = get_or_create_product(db_conn, specs_128)

    assert product_id_256 != product_id_128
    count = db_conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    assert count == 2


def test_needs_review_does_not_create_product(db_conn):
    specs = extract_specs("Promoção imperdível, corre que acaba rápido!")

    product_id, decision = get_or_create_product(db_conn, specs)

    assert product_id is None
    assert decision.decision == DECISION_NEEDS_REVIEW
    count = db_conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    assert count == 0


def test_repeated_match_updates_last_seen_at(db_conn):
    specs = extract_specs("Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90")
    product_id, _ = get_or_create_product(db_conn, specs)
    original_last_seen = db_conn.execute(
        "SELECT last_seen_at FROM products WHERE id = ?", (product_id,)
    ).fetchone()["last_seen_at"]

    get_or_create_product(db_conn, specs)

    updated_last_seen = db_conn.execute(
        "SELECT last_seen_at FROM products WHERE id = ?", (product_id,)
    ).fetchone()["last_seen_at"]
    assert updated_last_seen >= original_last_seen
