import sqlite3
from typing import Optional


def list_promotions(conn: sqlite3.Connection, *, status: Optional[str] = None,
                     since: Optional[str] = None, chat_title: Optional[str] = None,
                     matched_alert_id: Optional[int] = None,
                     bug_only: bool = False, limit: int = 200) -> list:
    query = "SELECT * FROM promotions WHERE 1=1"
    params: list = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if since:
        query += " AND created_at >= ?"
        params.append(since)
    if chat_title:
        query += " AND source_chat_title = ?"
        params.append(chat_title)
    if matched_alert_id:
        query += " AND matched_alert_id = ?"
        params.append(matched_alert_id)
    if bug_only:
        query += (
            " AND matched_alert_id IN (SELECT id FROM alerts WHERE bug_mode = 1)"
        )

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    return conn.execute(query, params).fetchall()


def list_raw_messages(conn: sqlite3.Connection, *, since: Optional[str] = None,
                       limit: int = 200) -> list:
    query = "SELECT * FROM raw_messages WHERE 1=1"
    params: list = []
    if since:
        query += " AND created_at >= ?"
        params.append(since)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()


def dashboard_counts(conn: sqlite3.Connection, *, since: str) -> dict:
    approved = conn.execute(
        "SELECT COUNT(*) FROM promotions WHERE status = 'APPROVED' AND created_at >= ?",
        (since,),
    ).fetchone()[0]
    ignored = conn.execute(
        "SELECT COUNT(*) FROM promotions WHERE status = 'IGNORED' AND created_at >= ?",
        (since,),
    ).fetchone()[0]
    duplicated = conn.execute(
        "SELECT COUNT(*) FROM promotion_occurrences WHERE created_at >= ?",
        (since,),
    ).fetchone()[0]
    notified = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE sent_at >= ?",
        (since,),
    ).fetchone()[0]
    bugs = conn.execute(
        """
        SELECT COUNT(*) FROM promotions p
        JOIN alerts a ON a.id = p.matched_alert_id
        WHERE a.bug_mode = 1 AND p.created_at >= ?
        """,
        (since,),
    ).fetchone()[0]

    top_groups = conn.execute(
        """
        SELECT source_chat_title, COUNT(*) as total
        FROM promotions
        WHERE created_at >= ? AND source_chat_title IS NOT NULL
        GROUP BY source_chat_title
        ORDER BY total DESC
        LIMIT 5
        """,
        (since,),
    ).fetchall()

    return {
        "approved": approved,
        "ignored": ignored,
        "duplicated": duplicated,
        "notified": notified,
        "bugs": bugs,
        "top_groups": top_groups,
    }
