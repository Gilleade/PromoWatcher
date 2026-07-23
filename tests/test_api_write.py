import json

from app.database import (
    insert_match_queue_item,
    insert_product,
    insert_promotion,
    insert_raw_message,
)


def _seed_product(conn, **overrides):
    defaults = dict(canonical_title="Motorola Moto G56 5G 256GB", variant_key="motorola|g56|256|8",
                     image_url="/media/moto-g56.jpg",
                     brand="motorola", model="moto g56 5g", storage_gb=256, ram_gb=8)
    defaults.update(overrides)
    return insert_product(conn, **defaults)


def test_favorite_add_and_remove(api_client):
    client, conn = api_client
    product_id = _seed_product(conn)

    response = client.post(f"/api/v1/products/{product_id}/favorite")
    assert response.status_code == 200
    assert response.json()["is_favorite"] is True

    favorites_response = client.get("/api/v1/favorites")
    assert len(favorites_response.json()) == 1

    response = client.delete(f"/api/v1/products/{product_id}/favorite")
    assert response.json()["is_favorite"] is False
    assert client.get("/api/v1/favorites").json() == []


def test_favorite_404_when_product_missing(api_client):
    client, _ = api_client
    response = client.post("/api/v1/products/9999/favorite")
    assert response.status_code == 404


def test_set_product_alert(api_client):
    client, conn = api_client
    product_id = _seed_product(conn)

    response = client.post(f"/api/v1/products/{product_id}/alert",
                            json={"enabled": True, "max_price": 999.90, "send_to_telegram": True})
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["max_price"] == 999.90

    row = conn.execute("SELECT * FROM product_alerts WHERE product_id = ?", (product_id,)).fetchone()
    assert row["enabled"] == 1
    assert row["max_price"] == 999.90


def test_block_and_unblock_product(api_client):
    client, conn = api_client
    product_id = _seed_product(conn)

    response = client.post(f"/api/v1/products/{product_id}/block")
    assert response.json()["status"] == "BLOCKED"
    assert conn.execute("SELECT status FROM products WHERE id = ?", (product_id,)).fetchone()["status"] == "BLOCKED"

    # produto bloqueado nao aparece mais no feed
    assert client.get("/api/v1/feed").json() == []

    response = client.post(f"/api/v1/products/{product_id}/unblock")
    assert response.json()["status"] == "ACTIVE"
    assert len(client.get("/api/v1/feed").json()) == 1


def test_merge_products(api_client):
    client, conn = api_client
    target_id = _seed_product(conn, canonical_title="Moto G56 256GB (correto)")
    source_id = _seed_product(
        conn, canonical_title="Moto G56 256GB (duplicado)", variant_key="motorola|g56|256|8|dup",
    )
    raw_id = insert_raw_message(
        conn, telegram_message_id=1, chat_id=1, chat_title="Grupo", sender_id=None,
        message_text="Moto G56", message_date="2026-07-16T10:00:00",
    )
    promo_id = insert_promotion(conn, raw_message_id=raw_id, price=999.90, status="APPROVED")
    conn.execute("UPDATE promotions SET product_id = ? WHERE id = ?", (source_id, promo_id))
    conn.commit()

    response = client.post(f"/api/v1/products/{target_id}/merge", json={"source_product_id": source_id})
    assert response.status_code == 200
    assert response.json() == {"source_product_id": source_id, "target_product_id": target_id}

    source_row = conn.execute("SELECT * FROM products WHERE id = ?", (source_id,)).fetchone()
    assert source_row["status"] == "MERGED"
    assert source_row["merged_into_product_id"] == target_id

    promo_row = conn.execute("SELECT product_id FROM promotions WHERE id = ?", (promo_id,)).fetchone()
    assert promo_row["product_id"] == target_id


def test_merge_rejects_self_merge(api_client):
    client, conn = api_client
    product_id = _seed_product(conn)
    response = client.post(f"/api/v1/products/{product_id}/merge", json={"source_product_id": product_id})
    assert response.status_code == 400


def test_admin_list_products_filters_by_status(api_client):
    client, conn = api_client
    active_id = _seed_product(conn)
    blocked_id = _seed_product(conn, canonical_title="Bloqueado", variant_key="x|y|1|1")
    client.post(f"/api/v1/products/{blocked_id}/block")

    response = client.get("/api/v1/admin/products", params={"status": "BLOCKED"})
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == blocked_id


def test_admin_match_queue_and_resolve_assign(api_client):
    client, conn = api_client
    target_id = _seed_product(conn)
    raw_id = insert_raw_message(
        conn, telegram_message_id=1, chat_id=1, chat_title="Grupo", sender_id=None,
        message_text="Produto ambiguo", message_date="2026-07-16T10:00:00",
    )
    promo_id = insert_promotion(conn, raw_message_id=raw_id, price=100.0, status="APPROVED")
    queue_id = insert_match_queue_item(
        conn, promotion_id=promo_id,
        extracted_specs_json=json.dumps({"brand": None, "model": None}),
        candidate_products_json="[]",
    )

    queue_response = client.get("/api/v1/admin/match-queue", params={"status": "PENDING"})
    assert len(queue_response.json()) == 1

    resolve_response = client.post(
        f"/api/v1/admin/match-queue/{queue_id}/resolve",
        json={"action": "assign", "product_id": target_id},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json() == {"action": "assign", "product_id": target_id}

    promo_row = conn.execute("SELECT product_id, product_match_status FROM promotions WHERE id = ?", (promo_id,)).fetchone()
    assert promo_row["product_id"] == target_id
    assert promo_row["product_match_status"] == "MANUAL_MATCH"

    assert client.get("/api/v1/admin/match-queue", params={"status": "PENDING"}).json() == []


def test_admin_match_queue_resolve_create_new(api_client):
    client, conn = api_client
    raw_id = insert_raw_message(
        conn, telegram_message_id=1, chat_id=1, chat_title="Grupo", sender_id=None,
        message_text="Produto ambiguo", message_date="2026-07-16T10:00:00",
    )
    promo_id = insert_promotion(conn, raw_message_id=raw_id, price=100.0, status="APPROVED")
    queue_id = insert_match_queue_item(
        conn, promotion_id=promo_id,
        extracted_specs_json=json.dumps({"brand": "dell", "model": "inspiron", "storage_gb": 256, "ram_gb": 8}),
        candidate_products_json="[]",
    )

    response = client.post(f"/api/v1/admin/match-queue/{queue_id}/resolve", json={"action": "create_new"})
    assert response.status_code == 200
    new_product_id = response.json()["product_id"]
    assert new_product_id is not None

    product = conn.execute("SELECT * FROM products WHERE id = ?", (new_product_id,)).fetchone()
    assert product["brand"] == "dell"


def test_coupons_endpoint_lists_active_coupons(api_client):
    client, conn = api_client
    raw_id = insert_raw_message(
        conn, telegram_message_id=1, chat_id=1, chat_title="Grupo", sender_id=None,
        message_text="Cupom BUG10", message_date="2026-07-16T10:00:00",
    )
    from app.database import insert_coupon
    insert_coupon(conn, raw_message_id=raw_id, dedupe_key="code:BUG10", code="BUG10")

    response = client.get("/api/v1/coupons")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["code"] == "BUG10"
