from app.database import insert_product
from app.products.product_service import (
    BUG_DEVIATION_PERCENT_THRESHOLD,
    MIN_HISTORY_POINTS_FOR_BUG_DETECTION,
    evaluate_bug_by_deviation,
    record_price_point,
)


def _seed_product(conn, **overrides):
    defaults = dict(canonical_title="Produto Teste", variant_key="teste|teste|1|1")
    defaults.update(overrides)
    return insert_product(conn, **defaults)


def test_no_bug_detection_below_minimum_history(db_conn):
    product_id = _seed_product(db_conn)
    for price in [1000.0, 950.0, 1020.0]:  # só 3 pontos, abaixo do mínimo
        record_price_point(db_conn, product_id=product_id, price=price)

    is_bug, deviation = evaluate_bug_by_deviation(db_conn, product_id, 100.0)
    assert is_bug is False
    assert deviation is None


def test_bug_detected_when_price_far_below_average(db_conn):
    product_id = _seed_product(db_conn)
    for price in [1000.0, 980.0, 1020.0, 990.0, 1010.0]:
        record_price_point(db_conn, product_id=product_id, price=price)

    is_bug, deviation = evaluate_bug_by_deviation(db_conn, product_id, 500.0)  # ~50% abaixo da média
    assert is_bug is True
    assert deviation >= BUG_DEVIATION_PERCENT_THRESHOLD


def test_no_bug_when_price_close_to_average(db_conn):
    product_id = _seed_product(db_conn)
    for price in [1000.0, 980.0, 1020.0, 990.0, 1010.0]:
        record_price_point(db_conn, product_id=product_id, price=price)

    is_bug, deviation = evaluate_bug_by_deviation(db_conn, product_id, 970.0)
    assert is_bug is False
    assert deviation < BUG_DEVIATION_PERCENT_THRESHOLD


def test_record_price_point_marks_history_row_as_bug_candidate(db_conn):
    product_id = _seed_product(db_conn)
    for price in [1000.0, 980.0, 1020.0, 990.0, 1010.0]:
        record_price_point(db_conn, product_id=product_id, price=price)

    result = record_price_point(db_conn, product_id=product_id, price=500.0)

    assert result.is_bug_candidate is True
    row = db_conn.execute(
        "SELECT * FROM product_price_history WHERE id = ?", (result.price_history_id,)
    ).fetchone()
    assert row["is_bug_candidate"] == 1
    assert row["price"] == 500.0


def test_record_price_point_updates_product_last_and_lowest_price(db_conn):
    product_id = _seed_product(db_conn)
    record_price_point(db_conn, product_id=product_id, price=1000.0)
    record_price_point(db_conn, product_id=product_id, price=800.0)
    record_price_point(db_conn, product_id=product_id, price=900.0)

    product = db_conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    assert product["last_price"] == 900.0
    assert product["lowest_price_ever"] == 800.0


def test_min_history_constant_matches_plan():
    assert MIN_HISTORY_POINTS_FOR_BUG_DETECTION == 5
