from app.database import insert_product
from app.products.matcher import DECISION_AUTO_MATCH, DECISION_AUTO_NEW, DECISION_NEEDS_REVIEW
from app.products.product_service import attach_product_image, get_or_create_product
from app.products.spec_extractor import extract_specs


def test_get_or_create_creates_new_product_first_time(db_conn):
    specs = extract_specs("Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90")

    product_id, decision = get_or_create_product(db_conn, specs)

    assert product_id is not None
    assert decision.decision == DECISION_AUTO_NEW
    row = db_conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    assert row["brand"] == "motorola"
    assert row["storage_gb"] == 256


def test_canonical_title_starts_with_category_prefix(db_conn):
    # bug real: título ficava só "Asus Tuf A15 Fa506Ncg Hn216 512GB 8GB RAM",
    # sem deixar claro que é um notebook.
    specs = extract_specs("Notebook Asus Tuf A15 FA506NCG HN216 512GB 8GB RAM por R$ 4.094,00")

    product_id, _ = get_or_create_product(db_conn, specs)

    row = db_conn.execute("SELECT canonical_title FROM products WHERE id = ?", (product_id,)).fetchone()
    assert row["canonical_title"].startswith("Notebook ")


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


def test_attach_product_image_sets_image_url_and_inserts_row(db_conn):
    product_id = insert_product(db_conn, canonical_title="Produto Teste", variant_key="t|t|1|1")

    attach_product_image(db_conn, product_id=product_id, local_path="data/images/1_2_3.jpg")

    product = db_conn.execute("SELECT image_url FROM products WHERE id = ?", (product_id,)).fetchone()
    assert product["image_url"] == "/media/1_2_3.jpg"
    image = db_conn.execute(
        "SELECT * FROM product_images WHERE product_id = ?", (product_id,)
    ).fetchone()
    assert image["local_path"] == "data/images/1_2_3.jpg"
    assert image["is_primary"] == 1


def test_attach_product_image_second_call_does_not_replace_primary(db_conn):
    product_id = insert_product(db_conn, canonical_title="Produto Teste", variant_key="t|t|1|1")
    attach_product_image(db_conn, product_id=product_id, local_path="data/images/1_2_3.jpg")

    attach_product_image(db_conn, product_id=product_id, local_path="data/images/4_5_6.jpg")

    product = db_conn.execute("SELECT image_url FROM products WHERE id = ?", (product_id,)).fetchone()
    assert product["image_url"] == "/media/1_2_3.jpg"
    count = db_conn.execute(
        "SELECT COUNT(*) FROM product_images WHERE product_id = ?", (product_id,)
    ).fetchone()[0]
    assert count == 2
