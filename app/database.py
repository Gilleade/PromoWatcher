import os
import sqlite3
from typing import Optional

from app.migrations import apply_pending

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection(db_path: str, *, check_same_thread: bool = True) -> sqlite3.Connection:
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(db_path: str) -> sqlite3.Connection:
    conn = get_connection(db_path)
    if db_path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    apply_pending(conn)
    return conn


def insert_raw_message(conn: sqlite3.Connection, *, telegram_message_id: int, chat_id: int,
                        chat_title: Optional[str], sender_id: Optional[int], message_text: str,
                        message_date: str, has_media: bool = False,
                        media_type: Optional[str] = None, raw_json: Optional[str] = None) -> int:
    cur = conn.execute(
        """
        INSERT INTO raw_messages
            (telegram_message_id, chat_id, chat_title, sender_id, message_text,
             message_date, has_media, media_type, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (telegram_message_id, chat_id, chat_title, sender_id, message_text,
         message_date, int(has_media), media_type, raw_json),
    )
    conn.commit()
    return cur.lastrowid


def insert_promotion(conn: sqlite3.Connection, *, raw_message_id: int, title_guess=None,
                      price=None, old_price=None, discount_percent=None, coupon=None,
                      installment_count=None, installment_price=None, installment_no_interest=None,
                      source_chat_title=None, original_links=None, selected_original_url=None,
                      resolved_url=None, clean_url=None, link_status=None, store_domain=None,
                      dedupe_key=None, status=None, score=None, matched_alert_id=None) -> int:
    cur = conn.execute(
        """
        INSERT INTO promotions
            (raw_message_id, title_guess, price, old_price, discount_percent, coupon,
             installment_count, installment_price, installment_no_interest,
             source_chat_title, original_links, selected_original_url, resolved_url,
             clean_url, link_status, store_domain, dedupe_key, status, score, matched_alert_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (raw_message_id, title_guess, price, old_price, discount_percent, coupon,
         installment_count, installment_price,
         None if installment_no_interest is None else int(installment_no_interest),
         source_chat_title, original_links, selected_original_url, resolved_url,
         clean_url, link_status, store_domain, dedupe_key, status, score, matched_alert_id),
    )
    conn.commit()
    return cur.lastrowid


def find_promotion_by_dedupe_key(conn: sqlite3.Connection, dedupe_key: str) -> Optional[sqlite3.Row]:
    cur = conn.execute("SELECT * FROM promotions WHERE dedupe_key = ? LIMIT 1", (dedupe_key,))
    return cur.fetchone()


def insert_occurrence(conn: sqlite3.Connection, *, promotion_id: int, raw_message_id: int,
                       chat_title: Optional[str], message_date: str,
                       original_url: Optional[str] = None) -> int:
    cur = conn.execute(
        """
        INSERT INTO promotion_occurrences
            (promotion_id, raw_message_id, chat_title, message_date, original_url)
        VALUES (?, ?, ?, ?, ?)
        """,
        (promotion_id, raw_message_id, chat_title, message_date, original_url),
    )
    conn.execute(
        """
        UPDATE promotions
        SET repeat_count = repeat_count + 1, last_seen_at = datetime('now')
        WHERE id = ?
        """,
        (promotion_id,),
    )
    conn.commit()
    return cur.lastrowid


def insert_notification(conn: sqlite3.Connection, *, promotion_id: int, alert_id: Optional[int],
                         channel: str, message_sent: str, status: str = "SENT",
                         error_message: Optional[str] = None,
                         product_alert_id: Optional[int] = None) -> int:
    cur = conn.execute(
        """
        INSERT INTO notifications
            (promotion_id, alert_id, product_alert_id, channel, message_sent, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (promotion_id, alert_id, product_alert_id, channel, message_sent, status, error_message),
    )
    conn.commit()
    return cur.lastrowid


def upsert_alert(conn: sqlite3.Connection, *, name: str, enabled: bool, alert_type: str,
                  required_terms, optional_terms, excluded_terms, min_price, max_price,
                  min_discount_percent, bug_mode: bool, min_score: int,
                  send_to_telegram: bool) -> int:
    """Insere ou atualiza um alerta por nome (alerts.json é a fonte da verdade)."""
    existing = conn.execute("SELECT id FROM alerts WHERE name = ?", (name,)).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE alerts SET enabled=?, alert_type=?, required_terms=?, optional_terms=?,
                excluded_terms=?, min_price=?, max_price=?, min_discount_percent=?,
                bug_mode=?, min_score=?, send_to_telegram=?, updated_at=datetime('now')
            WHERE id = ?
            """,
            (int(enabled), alert_type, required_terms, optional_terms, excluded_terms,
             min_price, max_price, min_discount_percent, int(bug_mode), min_score,
             int(send_to_telegram), existing["id"]),
        )
        conn.commit()
        return existing["id"]

    cur = conn.execute(
        """
        INSERT INTO alerts
            (name, enabled, alert_type, required_terms, optional_terms, excluded_terms,
             min_price, max_price, min_discount_percent, bug_mode, min_score, send_to_telegram)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, int(enabled), alert_type, required_terms, optional_terms, excluded_terms,
         min_price, max_price, min_discount_percent, int(bug_mode), min_score,
         int(send_to_telegram)),
    )
    conn.commit()
    return cur.lastrowid


def insert_product(conn: sqlite3.Connection, *, canonical_title: str, variant_key: str,
                    category: Optional[str] = None, brand: Optional[str] = None,
                    model: Optional[str] = None, variant_label: Optional[str] = None,
                    storage_gb: Optional[int] = None, ram_gb: Optional[int] = None,
                    release_year: Optional[int] = None, image_url: Optional[str] = None) -> int:
    cur = conn.execute(
        """
        INSERT INTO products
            (canonical_title, category, brand, model, variant_label, storage_gb, ram_gb,
             release_year, variant_key, image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (canonical_title, category, brand, model, variant_label, storage_gb, ram_gb,
         release_year, variant_key, image_url),
    )
    conn.commit()
    return cur.lastrowid


def find_product_by_variant_key(conn: sqlite3.Connection, variant_key: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM products WHERE variant_key = ? AND status = 'ACTIVE' LIMIT 1",
        (variant_key,),
    ).fetchone()


def find_product_by_variant_key_any_status(
    conn: sqlite3.Connection, variant_key: str,
) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM products
        WHERE variant_key = ?
        ORDER BY CASE status WHEN 'ACTIVE' THEN 0 WHEN 'BLOCKED' THEN 1 ELSE 2 END
        LIMIT 1
        """,
        (variant_key,),
    ).fetchone()


def list_active_products(conn: sqlite3.Connection, *, brand: Optional[str] = None,
                          category: Optional[str] = None) -> list:
    query = "SELECT * FROM products WHERE status = 'ACTIVE'"
    params: list = []
    if brand:
        query += " AND brand = ?"
        params.append(brand)
    elif category:
        query += " AND category = ?"
        params.append(category)
    return conn.execute(query, params).fetchall()


def touch_product_seen(conn: sqlite3.Connection, product_id: int) -> None:
    conn.execute(
        "UPDATE products SET last_seen_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
        (product_id,),
    )
    conn.commit()


def update_promotion_product_match(conn: sqlite3.Connection, *, promotion_id: int,
                                    product_id: Optional[int], match_status: str,
                                    confidence: Optional[float]) -> None:
    conn.execute(
        """
        UPDATE promotions
        SET product_id = ?, product_match_status = ?, product_match_confidence = ?
        WHERE id = ?
        """,
        (product_id, match_status, confidence, promotion_id),
    )
    conn.commit()


def insert_match_queue_item(conn: sqlite3.Connection, *, promotion_id: int,
                             extracted_specs_json: str,
                             candidate_products_json: Optional[str] = None) -> int:
    cur = conn.execute(
        """
        INSERT INTO product_match_queue
            (promotion_id, extracted_specs_json, candidate_products_json)
        VALUES (?, ?, ?)
        """,
        (promotion_id, extracted_specs_json, candidate_products_json),
    )
    conn.commit()
    return cur.lastrowid


def list_price_history(conn: sqlite3.Connection, product_id: int) -> list:
    return conn.execute(
        "SELECT * FROM product_price_history WHERE product_id = ? ORDER BY recorded_at",
        (product_id,),
    ).fetchall()


def insert_price_history_point(conn: sqlite3.Connection, *, product_id: int, price: float,
                                promotion_id: Optional[int] = None, old_price: Optional[float] = None,
                                coupon: Optional[str] = None, store_domain: Optional[str] = None,
                                source_chat_title: Optional[str] = None,
                                is_bug_candidate: bool = False,
                                deviation_percent: Optional[float] = None) -> int:
    cur = conn.execute(
        """
        INSERT INTO product_price_history
            (product_id, promotion_id, price, old_price, coupon, store_domain,
             source_chat_title, is_bug_candidate, deviation_percent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (product_id, promotion_id, price, old_price, coupon, store_domain,
         source_chat_title, int(is_bug_candidate), deviation_percent),
    )
    conn.commit()
    return cur.lastrowid


def update_product_price_stats(conn: sqlite3.Connection, product_id: int, price: float, *,
                                installment_count: Optional[int] = None,
                                installment_price: Optional[float] = None,
                                installment_no_interest: Optional[bool] = None) -> None:
    row = conn.execute(
        "SELECT lowest_price_ever FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    is_new_low = row["lowest_price_ever"] is None or price < row["lowest_price_ever"]
    # COALESCE nas 3 colunas de parcelamento: quando a mensagem atual não
    # trouxer parcelamento, mantém o último conhecido em vez de apagar —
    # mensagens repostadas nem sempre repetem a linha "Nx de R$Y".
    installment_no_interest_int = None if installment_no_interest is None else int(installment_no_interest)
    if is_new_low:
        conn.execute(
            """
            UPDATE products
            SET last_price = ?, last_price_at = datetime('now'),
                lowest_price_ever = ?, lowest_price_ever_at = datetime('now'),
                last_installment_count = COALESCE(?, last_installment_count),
                last_installment_price = COALESCE(?, last_installment_price),
                last_installment_no_interest = COALESCE(?, last_installment_no_interest),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (price, price, installment_count, installment_price,
             installment_no_interest_int, product_id),
        )
    else:
        conn.execute(
            """
            UPDATE products
            SET last_price = ?, last_price_at = datetime('now'),
                last_installment_count = COALESCE(?, last_installment_count),
                last_installment_price = COALESCE(?, last_installment_price),
                last_installment_no_interest = COALESCE(?, last_installment_no_interest),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (price, installment_count, installment_price, installment_no_interest_int, product_id),
        )
    conn.commit()


def insert_product_image(conn: sqlite3.Connection, *, product_id: int,
                          local_path: Optional[str] = None, image_url: Optional[str] = None,
                          source: str = "TELEGRAM_MEDIA", is_primary: bool = False) -> int:
    cur = conn.execute(
        """
        INSERT INTO product_images (product_id, image_url, local_path, source, is_primary)
        VALUES (?, ?, ?, ?, ?)
        """,
        (product_id, image_url, local_path, source, int(is_primary)),
    )
    conn.commit()
    return cur.lastrowid


def update_product_image_url_if_null(conn: sqlite3.Connection, product_id: int, image_url: str) -> bool:
    """Só grava products.image_url se ainda estiver NULL — nunca sobrescreve
    uma imagem já conhecida por causa de um reenvio/edição posterior sem
    foto (ou com foto diferente). Retorna True quando esta chamada foi quem
    definiu o valor (usado para marcar a linha em product_images como
    is_primary)."""
    cur = conn.execute(
        "UPDATE products SET image_url = ?, updated_at = datetime('now') "
        "WHERE id = ? AND image_url IS NULL",
        (image_url, product_id),
    )
    conn.commit()
    return cur.rowcount > 0


def update_promotion_price(conn: sqlite3.Connection, *, promotion_id: int, price: float,
                            old_price: Optional[float] = None,
                            installment_count: Optional[int] = None,
                            installment_price: Optional[float] = None,
                            installment_no_interest: Optional[bool] = None) -> None:
    conn.execute(
        """
        UPDATE promotions
        SET price = ?, old_price = ?, installment_count = ?, installment_price = ?,
            installment_no_interest = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (price, old_price, installment_count, installment_price,
         None if installment_no_interest is None else int(installment_no_interest), promotion_id),
    )
    conn.commit()


def get_next_pending_match_queue_item(conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM product_match_queue WHERE status = 'PENDING' ORDER BY created_at LIMIT 1"
    ).fetchone()


def update_match_queue_status(conn: sqlite3.Connection, item_id: int, *, status: str,
                               attempts: int, result_json: Optional[str] = None,
                               error_message: Optional[str] = None) -> None:
    conn.execute(
        """
        UPDATE product_match_queue
        SET status = ?, attempts = ?, result_json = ?, error_message = ?, processed_at = datetime('now')
        WHERE id = ?
        """,
        (status, attempts, result_json, error_message, item_id),
    )
    conn.commit()


def fetch_products_by_ids(conn: sqlite3.Connection, product_ids: list) -> list:
    if not product_ids:
        return []
    placeholders = ",".join("?" * len(product_ids))
    return conn.execute(
        f"SELECT * FROM products WHERE id IN ({placeholders})", product_ids
    ).fetchall()


def get_promotion_with_raw_text(conn: sqlite3.Connection, promotion_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT p.*, rm.message_text AS raw_message_text
        FROM promotions p
        JOIN raw_messages rm ON rm.id = p.raw_message_id
        WHERE p.id = ?
        """,
        (promotion_id,),
    ).fetchone()


def insert_coupon(conn: sqlite3.Connection, *, raw_message_id: int, dedupe_key: str,
                   code: Optional[str] = None, discount_label: Optional[str] = None,
                   description: Optional[str] = None, store_name: Optional[str] = None,
                   store_domain: Optional[str] = None, url: Optional[str] = None,
                   source_chat_title: Optional[str] = None) -> int:
    cur = conn.execute(
        """
        INSERT INTO coupons_standalone
            (raw_message_id, code, discount_label, description, store_name,
             store_domain, url, dedupe_key, source_chat_title)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (raw_message_id, code, discount_label, description, store_name,
         store_domain, url, dedupe_key, source_chat_title),
    )
    conn.commit()
    return cur.lastrowid


def find_coupon_by_dedupe_key(conn: sqlite3.Connection, dedupe_key: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM coupons_standalone WHERE dedupe_key = ? AND status = 'ACTIVE' LIMIT 1",
        (dedupe_key,),
    ).fetchone()


def touch_coupon_seen(conn: sqlite3.Connection, coupon_id: int) -> None:
    conn.execute(
        """
        UPDATE coupons_standalone
        SET repeat_count = repeat_count + 1, last_seen_at = datetime('now'), updated_at = datetime('now')
        WHERE id = ?
        """,
        (coupon_id,),
    )
    conn.commit()


def list_active_coupons(conn: sqlite3.Connection, *, status: str = "ACTIVE", limit: int = 100) -> list:
    return conn.execute(
        "SELECT * FROM coupons_standalone WHERE status = ? ORDER BY last_seen_at DESC LIMIT ?",
        (status, limit),
    ).fetchall()


def insert_favorite(conn: sqlite3.Connection, product_id: int) -> None:
    conn.execute("INSERT OR IGNORE INTO favorites (product_id) VALUES (?)", (product_id,))
    conn.commit()


def delete_favorite(conn: sqlite3.Connection, product_id: int) -> None:
    conn.execute("DELETE FROM favorites WHERE product_id = ?", (product_id,))
    conn.commit()


def list_favorite_products(conn: sqlite3.Connection) -> list:
    return conn.execute(
        """
        SELECT p.* FROM products p
        JOIN favorites f ON f.product_id = p.id
        ORDER BY f.created_at DESC
        """
    ).fetchall()


def find_matching_product_alert(
    conn: sqlite3.Connection, *, product_id: Optional[int], price: Optional[float],
) -> Optional[sqlite3.Row]:
    if product_id is None or price is None:
        return None
    return conn.execute(
        """
        SELECT pa.*, p.canonical_title
        FROM product_alerts pa
        JOIN products p ON p.id = pa.product_id
        WHERE pa.product_id = ?
          AND pa.enabled = 1
          AND p.status = 'ACTIVE'
          AND (pa.max_price IS NULL OR ? <= pa.max_price)
        LIMIT 1
        """,
        (product_id, price),
    ).fetchone()


def update_promotion_decision(
    conn: sqlite3.Connection, *, promotion_id: int, status: str, score: Optional[int] = None,
) -> None:
    conn.execute(
        "UPDATE promotions SET status = ?, score = ?, updated_at = datetime('now') WHERE id = ?",
        (status, score, promotion_id),
    )
    conn.commit()


def upsert_product_alert(conn: sqlite3.Connection, *, product_id: int, enabled: bool,
                          max_price: Optional[float] = None, send_to_telegram: bool = True) -> int:
    existing = conn.execute(
        "SELECT id FROM product_alerts WHERE product_id = ?", (product_id,)
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE product_alerts
            SET enabled = ?, max_price = ?, send_to_telegram = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (int(enabled), max_price, int(send_to_telegram), existing["id"]),
        )
        conn.commit()
        return existing["id"]

    cur = conn.execute(
        """
        INSERT INTO product_alerts (product_id, enabled, max_price, send_to_telegram)
        VALUES (?, ?, ?, ?)
        """,
        (product_id, int(enabled), max_price, int(send_to_telegram)),
    )
    conn.commit()
    return cur.lastrowid


def update_product_status(conn: sqlite3.Connection, product_id: int, status: str) -> None:
    conn.execute(
        "UPDATE products SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, product_id),
    )
    conn.commit()


def list_products_admin(conn: sqlite3.Connection, *, status: Optional[str] = None,
                         search: Optional[str] = None, limit: int = 100) -> list:
    query = "SELECT * FROM products WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if search:
        query += " AND canonical_title LIKE ?"
        params.append(f"%{search}%")
    query += " ORDER BY last_seen_at DESC LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()


def list_match_queue(conn: sqlite3.Connection, *, status: Optional[str] = None, limit: int = 100) -> list:
    query = "SELECT * FROM product_match_queue WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()


def get_match_queue_item(conn: sqlite3.Connection, item_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM product_match_queue WHERE id = ?", (item_id,)).fetchone()


def insert_product_merge_record(conn: sqlite3.Connection, *, source_product_id: int,
                                 target_product_id: int, reason: Optional[str] = None) -> int:
    cur = conn.execute(
        "INSERT INTO product_merges (source_product_id, target_product_id, reason) VALUES (?, ?, ?)",
        (source_product_id, target_product_id, reason),
    )
    conn.commit()
    return cur.lastrowid


def reassign_promotions_to_product(conn: sqlite3.Connection, *, source_product_id: int,
                                    target_product_id: int) -> int:
    cur = conn.execute(
        "UPDATE promotions SET product_id = ? WHERE product_id = ?",
        (target_product_id, source_product_id),
    )
    conn.commit()
    return cur.rowcount


def reassign_price_history_to_product(conn: sqlite3.Connection, *, source_product_id: int,
                                       target_product_id: int) -> int:
    cur = conn.execute(
        "UPDATE product_price_history SET product_id = ? WHERE product_id = ?",
        (target_product_id, source_product_id),
    )
    conn.commit()
    return cur.rowcount


def set_product_merged(conn: sqlite3.Connection, *, source_product_id: int, target_product_id: int) -> None:
    conn.execute(
        "UPDATE products SET status = 'MERGED', merged_into_product_id = ?, updated_at = datetime('now') WHERE id = ?",
        (target_product_id, source_product_id),
    )
    conn.commit()
