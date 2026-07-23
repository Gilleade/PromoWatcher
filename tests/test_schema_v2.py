import sqlite3

import pytest

from app.models import (
    Favorite,
    PriceHistoryPoint,
    Product,
    ProductAlert,
    ProductSpec,
    StandaloneCoupon,
)

NEW_TABLES = {
    "products",
    "product_specs",
    "product_price_history",
    "product_images",
    "favorites",
    "product_alerts",
    "coupons_standalone",
    "product_match_queue",
    "product_merges",
}


def test_new_catalog_tables_exist(db_conn):
    tables = {
        row["name"]
        for row in db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert NEW_TABLES.issubset(tables)


def test_promotions_has_product_columns(db_conn):
    cols = {row["name"] for row in db_conn.execute("PRAGMA table_info(promotions)").fetchall()}
    assert {"product_id", "product_match_status", "product_match_confidence", "listing_status"}.issubset(cols)


def test_notifications_has_product_alert_column(db_conn):
    cols = {row["name"] for row in db_conn.execute("PRAGMA table_info(notifications)").fetchall()}
    assert "product_alert_id" in cols


def test_products_table_defaults(db_conn):
    db_conn.execute(
        "INSERT INTO products (canonical_title, variant_key) VALUES (?, ?)",
        ("Motorola Moto G56 5G 256GB", "motorola|moto g56 5g|256|8"),
    )
    db_conn.commit()
    row = db_conn.execute("SELECT * FROM products").fetchone()
    assert row["status"] == "ACTIVE"
    assert row["canonical_title"] == "Motorola Moto G56 5G 256GB"


def test_product_specs_unique_constraint_per_product_key(db_conn):
    db_conn.execute(
        "INSERT INTO products (canonical_title, variant_key) VALUES (?, ?)", ("X", "x|x|x|x")
    )
    product_id = db_conn.execute("SELECT id FROM products").fetchone()["id"]
    db_conn.execute(
        "INSERT INTO product_specs (product_id, spec_key, spec_value) VALUES (?, 'color', 'preto')",
        (product_id,),
    )
    db_conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(
            "INSERT INTO product_specs (product_id, spec_key, spec_value) VALUES (?, 'color', 'branco')",
            (product_id,),
        )


def test_dataclasses_construct_with_expected_fields():
    product = Product(canonical_title="Moto G56 256GB", variant_key="motorola|moto g56|256|8")
    assert product.status == "ACTIVE"
    assert product.id is None

    spec = ProductSpec(product_id=1, spec_key="ram_gb", spec_value="8")
    assert spec.source == "DETERMINISTIC"

    point = PriceHistoryPoint(product_id=1, price=1093.90)
    assert point.is_bug_candidate is False

    favorite = Favorite(product_id=1)
    assert favorite.id is None

    alert = ProductAlert(product_id=1)
    assert alert.enabled is True

    coupon = StandaloneCoupon(raw_message_id=1, code="MOTO300")
    assert coupon.status == "ACTIVE"
