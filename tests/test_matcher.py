from app.database import insert_product
from app.products.matcher import (
    DECISION_AUTO_MATCH,
    DECISION_AUTO_NEW,
    DECISION_NEEDS_REVIEW,
    match_product,
)
from app.products.spec_extractor import build_variant_key, extract_specs


def _seed_product(conn, **overrides):
    defaults = dict(
        canonical_title="Motorola Moto G56 5G 256GB",
        variant_key="motorola|moto g56 5g|256|8",
        brand="motorola", model="moto g56 5g", storage_gb=256, ram_gb=8,
        category="smartphone",
    )
    defaults.update(overrides)
    return insert_product(conn, **defaults)


def test_exact_variant_key_match_is_auto_match(db_conn):
    product_id = _seed_product(db_conn)
    specs = extract_specs("Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90")

    decision = match_product(db_conn, specs)

    assert decision.decision == DECISION_AUTO_MATCH
    assert decision.product_id == product_id
    assert decision.confidence == 1.0


def test_same_product_different_wording_converges_to_same_product(db_conn):
    specs_a = extract_specs("Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90 no Magalu")
    decision_a = match_product(db_conn, specs_a)
    assert decision_a.decision == DECISION_AUTO_NEW

    product_id = insert_product(
        db_conn, canonical_title="Motorola Moto G56 5G 256GB",
        variant_key=build_variant_key(specs_a.brand, specs_a.model, specs_a.storage_gb, specs_a.ram_gb),
        brand=specs_a.brand, model=specs_a.model, storage_gb=specs_a.storage_gb, ram_gb=specs_a.ram_gb,
        category=specs_a.category,
    )

    specs_b = extract_specs("MOTOROLA MOTO G56 5G 256GB 8GB RAM - CUPOM DISPONIVEL")
    decision_b = match_product(db_conn, specs_b)

    assert decision_b.decision == DECISION_AUTO_MATCH
    assert decision_b.product_id == product_id


def test_different_storage_never_auto_matches(db_conn):
    _seed_product(db_conn, storage_gb=256, variant_key="motorola|moto g56 5g|256|8")
    specs_128 = extract_specs("Motorola Moto G56 5G 128GB 8GB RAM por R$ 899,90")

    decision = match_product(db_conn, specs_128)

    assert decision.decision != DECISION_AUTO_MATCH


def test_different_brand_never_auto_matches(db_conn):
    _seed_product(db_conn, brand="motorola", variant_key="motorola|moto g56 5g|256|8")
    specs = extract_specs("Samsung Galaxy A55 8/256GB por R$ 1.799,00")

    decision = match_product(db_conn, specs)

    assert decision.decision != DECISION_AUTO_MATCH


def test_incomplete_extraction_goes_to_needs_review(db_conn):
    specs = extract_specs("Promoção imperdível, corre que acaba rápido!")
    decision = match_product(db_conn, specs)
    assert decision.decision == DECISION_NEEDS_REVIEW


def test_no_candidates_and_complete_specs_creates_new(db_conn):
    specs = extract_specs("Notebook Dell Inspiron 15 8GB RAM 256GB SSD por R$ 2.999,00")
    decision = match_product(db_conn, specs)
    assert decision.decision == DECISION_AUTO_NEW


def test_similar_but_not_identical_model_lands_in_review_zone(db_conn):
    _seed_product(
        db_conn, brand="motorola", model="moto g55 5g", storage_gb=256, ram_gb=8,
        variant_key="motorola|moto g55 5g|256|8",
    )
    specs = extract_specs("Motorola Moto G54 5G 256GB 8GB RAM por R$ 999,90")

    decision = match_product(db_conn, specs)

    assert decision.decision in (DECISION_NEEDS_REVIEW, DECISION_AUTO_NEW)
    assert decision.decision != DECISION_AUTO_MATCH
