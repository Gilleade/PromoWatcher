import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.main import app
from app.database import (
    init_db,
    insert_price_history_point,
    insert_product,
    insert_promotion,
    insert_raw_message,
    update_promotion_product_match,
)


@pytest.fixture
def api_client(tmp_path):
    db_path = str(tmp_path / "api_test.sqlite3")
    setup_conn = init_db(db_path)

    def override_get_db():
        conn = init_db(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client, setup_conn
    app.dependency_overrides.clear()
    setup_conn.close()


def _seed_product_with_promotion(conn, *, canonical_title="Motorola Moto G56 5G 256GB",
                                  brand="motorola", price=1093.90):
    product_id = insert_product(
        conn, canonical_title=canonical_title, variant_key=f"{brand}|g56|256|8",
        brand=brand, model="moto g56 5g", storage_gb=256, ram_gb=8, category="smartphone",
    )
    raw_id = insert_raw_message(
        conn, telegram_message_id=1, chat_id=1, chat_title="Grupo Teste", sender_id=None,
        message_text="BUG: Moto G56 256GB", message_date="2026-07-16T10:00:00",
    )
    promotion_id = insert_promotion(
        conn, raw_message_id=raw_id, title_guess=canonical_title, price=price,
        coupon="MOTO300", store_domain="magazineluiza.com.br", link_status="CLEANED",
        clean_url="https://magazineluiza.com.br/produto", status="APPROVED",
    )
    update_promotion_product_match(
        conn, promotion_id=promotion_id, product_id=product_id,
        match_status="AUTO_NEW", confidence=1.0,
    )
    insert_price_history_point(conn, product_id=product_id, promotion_id=promotion_id, price=price)
    return product_id, promotion_id


def test_health_check(api_client):
    client, _ = api_client
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_feed_returns_seeded_products(api_client):
    client, conn = api_client
    _seed_product_with_promotion(conn)

    response = client.get("/api/v1/feed")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["canonical_title"] == "Motorola Moto G56 5G 256GB"
    assert data[0]["brand"] == "motorola"


def test_feed_filters_by_category(api_client):
    client, conn = api_client
    _seed_product_with_promotion(conn, canonical_title="Moto G56", brand="motorola")
    insert_product(
        conn, canonical_title="Notebook Dell Inspiron", variant_key="dell|inspiron|256|8",
        brand="dell", category="notebook",
    )

    response = client.get("/api/v1/feed", params={"category": "notebook"})
    data = response.json()
    assert len(data) == 1
    assert data[0]["canonical_title"] == "Notebook Dell Inspiron"


def test_feed_respects_limit(api_client):
    client, conn = api_client
    for i in range(5):
        insert_product(conn, canonical_title=f"Produto {i}", variant_key=f"x|{i}|1|1")

    response = client.get("/api/v1/feed", params={"limit": 2})
    assert len(response.json()) == 2


def test_get_product_detail_returns_full_profile(api_client):
    client, conn = api_client
    product_id, _ = _seed_product_with_promotion(conn)

    response = client.get(f"/api/v1/products/{product_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["canonical_title"] == "Motorola Moto G56 5G 256GB"
    assert data["latest_coupon"] == "MOTO300"
    assert data["latest_url"] == "https://magazineluiza.com.br/produto"
    assert data["is_favorite"] is False
    assert data["alert_enabled"] is False
    assert len(data["price_history"]) == 1


def test_get_product_detail_404_when_missing(api_client):
    client, _ = api_client
    response = client.get("/api/v1/products/9999")
    assert response.status_code == 404


def test_get_price_history_endpoint(api_client):
    client, conn = api_client
    product_id, _ = _seed_product_with_promotion(conn)

    response = client.get(f"/api/v1/products/{product_id}/price-history", params={"window": 30})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["price"] == 1093.90


def test_dashboard_summary_endpoint(api_client):
    client, conn = api_client
    _seed_product_with_promotion(conn)

    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["products_total"] == 1
    assert data["approved_today"] == 1


def test_openapi_docs_available(api_client):
    client, _ = api_client
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/feed" in response.json()["paths"]
