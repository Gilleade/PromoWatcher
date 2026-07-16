import sqlite3
from typing import Optional

from app.database import (
    list_active_coupons,
    list_favorite_products,
    list_match_queue,
    list_products_admin,
)


def list_favorites(conn: sqlite3.Connection) -> list:
    return list_favorite_products(conn)


def list_products_for_admin(conn: sqlite3.Connection, *, status: Optional[str] = None,
                             search: Optional[str] = None, limit: int = 100) -> list:
    return list_products_admin(conn, status=status, search=search, limit=limit)


def list_review_queue(conn: sqlite3.Connection, *, status: Optional[str] = None, limit: int = 100) -> list:
    return list_match_queue(conn, status=status, limit=limit)


def list_coupons(conn: sqlite3.Connection, *, status: str = "ACTIVE", limit: int = 100) -> list:
    return list_active_coupons(conn, status=status, limit=limit)


def list_feed_products(conn: sqlite3.Connection, *, category: Optional[str] = None,
                        limit: int = 50, offset: int = 0) -> list:
    query = "SELECT * FROM products WHERE status = 'ACTIVE'"
    params: list = []
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY last_seen_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return conn.execute(query, params).fetchall()


def get_product_row(conn: sqlite3.Connection, product_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()


def get_latest_promotion_for_product(conn: sqlite3.Connection, product_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM promotions WHERE product_id = ? ORDER BY created_at DESC LIMIT 1",
        (product_id,),
    ).fetchone()


def list_price_history_windowed(conn: sqlite3.Connection, product_id: int, *, days: int = 30) -> list:
    return conn.execute(
        """
        SELECT * FROM product_price_history
        WHERE product_id = ? AND recorded_at >= datetime('now', ?)
        ORDER BY recorded_at
        """,
        (product_id, f"-{days} days"),
    ).fetchall()


def price_window_stats(conn: sqlite3.Connection, product_id: int, *, days: int = 30) -> dict:
    rows = list_price_history_windowed(conn, product_id, days=days)
    prices = [row["price"] for row in rows]
    if not prices:
        return {"avg": None, "min": None, "max": None, "count": 0}
    return {
        "avg": sum(prices) / len(prices),
        "min": min(prices),
        "max": max(prices),
        "count": len(prices),
    }


def is_favorited(conn: sqlite3.Connection, product_id: int) -> bool:
    row = conn.execute("SELECT 1 FROM favorites WHERE product_id = ?", (product_id,)).fetchone()
    return row is not None


def get_product_alert(conn: sqlite3.Connection, product_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM product_alerts WHERE product_id = ?", (product_id,)
    ).fetchone()


def get_product_detail(conn: sqlite3.Connection, product_id: int) -> Optional[dict]:
    """Monta o dicionário completo do perfil de produto: dados do catálogo +
    promoção mais recente (link/cupom/loja atuais) + histórico de 30 dias +
    flags de favorito/alerta. Retorna None se o produto não existe."""
    product = get_product_row(conn, product_id)
    if product is None:
        return None

    latest_promotion = get_latest_promotion_for_product(conn, product_id)
    history_rows = list_price_history_windowed(conn, product_id, days=30)
    alert_row = get_product_alert(conn, product_id)

    return {
        "id": product["id"],
        "canonical_title": product["canonical_title"],
        "brand": product["brand"],
        "model": product["model"],
        "category": product["category"],
        "storage_gb": product["storage_gb"],
        "ram_gb": product["ram_gb"],
        "release_year": product["release_year"],
        "image_url": product["image_url"],
        "status": product["status"],
        "last_price": product["last_price"],
        "lowest_price_ever": product["lowest_price_ever"],
        "lowest_price_ever_at": product["lowest_price_ever_at"],
        "last_installment_count": product["last_installment_count"],
        "last_installment_price": product["last_installment_price"],
        "last_installment_no_interest": (
            bool(product["last_installment_no_interest"])
            if product["last_installment_no_interest"] is not None else None
        ),
        "latest_coupon": latest_promotion["coupon"] if latest_promotion else None,
        "latest_url": (
            (latest_promotion["clean_url"] or latest_promotion["resolved_url"]
             or latest_promotion["selected_original_url"])
            if latest_promotion else None
        ),
        "latest_store_domain": latest_promotion["store_domain"] if latest_promotion else None,
        "latest_link_status": latest_promotion["link_status"] if latest_promotion else None,
        "listing_status": latest_promotion["listing_status"] if latest_promotion else None,
        "is_favorite": is_favorited(conn, product_id),
        "alert_enabled": bool(alert_row["enabled"]) if alert_row else False,
        "price_history": [
            {
                "recorded_at": row["recorded_at"],
                "price": row["price"],
                "is_bug_candidate": bool(row["is_bug_candidate"]),
                "deviation_percent": row["deviation_percent"],
            }
            for row in history_rows
        ],
    }


def dashboard_summary(conn: sqlite3.Connection, *, since: str) -> dict:
    products_total = conn.execute(
        "SELECT COUNT(*) FROM products WHERE status = 'ACTIVE'"
    ).fetchone()[0]
    approved_today = conn.execute(
        "SELECT COUNT(*) FROM promotions WHERE status = 'APPROVED' AND created_at >= ?", (since,)
    ).fetchone()[0]
    notified_today = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE sent_at >= ?", (since,)
    ).fetchone()[0]
    duplicated_today = conn.execute(
        "SELECT COUNT(*) FROM promotion_occurrences WHERE created_at >= ?", (since,)
    ).fetchone()[0]
    bugs_today = conn.execute(
        "SELECT COUNT(*) FROM product_price_history WHERE is_bug_candidate = 1 AND recorded_at >= ?",
        (since,),
    ).fetchone()[0]
    coupons_active = conn.execute(
        "SELECT COUNT(*) FROM coupons_standalone WHERE status = 'ACTIVE'"
    ).fetchone()[0]
    pending_review = conn.execute(
        "SELECT COUNT(*) FROM product_match_queue WHERE status = 'PENDING'"
    ).fetchone()[0]

    return {
        "products_total": products_total,
        "approved_today": approved_today,
        "notified_today": notified_today,
        "duplicated_today": duplicated_today,
        "bugs_today": bugs_today,
        "coupons_active": coupons_active,
        "pending_review": pending_review,
    }
