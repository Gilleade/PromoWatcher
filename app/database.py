import os
import sqlite3
from typing import Optional

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection(db_path: str, *, check_same_thread: bool = True) -> sqlite3.Connection:
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> sqlite3.Connection:
    conn = get_connection(db_path)
    if db_path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
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
                      source_chat_title=None, original_links=None, selected_original_url=None,
                      resolved_url=None, clean_url=None, link_status=None, store_domain=None,
                      dedupe_key=None, status=None, score=None, matched_alert_id=None) -> int:
    cur = conn.execute(
        """
        INSERT INTO promotions
            (raw_message_id, title_guess, price, old_price, discount_percent, coupon,
             source_chat_title, original_links, selected_original_url, resolved_url,
             clean_url, link_status, store_domain, dedupe_key, status, score, matched_alert_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (raw_message_id, title_guess, price, old_price, discount_percent, coupon,
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
                         error_message: Optional[str] = None) -> int:
    cur = conn.execute(
        """
        INSERT INTO notifications
            (promotion_id, alert_id, channel, message_sent, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (promotion_id, alert_id, channel, message_sent, status, error_message),
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
