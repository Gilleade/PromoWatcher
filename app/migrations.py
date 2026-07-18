import sqlite3
from typing import List, Optional, Tuple

Migration = Tuple[str, str]

# Cada item é (id_unico, sql). Usado para mudanças que CREATE TABLE IF NOT
# EXISTS não cobre sozinho (ex.: ALTER TABLE ADD COLUMN, que não é
# idempotente no SQLite). Tabelas novas vão direto em app/schema.sql.
MIGRATIONS: List[Migration] = [
    ("0001_promotions_product_columns", """
        ALTER TABLE promotions ADD COLUMN product_id INTEGER REFERENCES products (id);
        ALTER TABLE promotions ADD COLUMN product_match_status TEXT DEFAULT 'UNMATCHED';
        ALTER TABLE promotions ADD COLUMN product_match_confidence REAL;
        ALTER TABLE promotions ADD COLUMN listing_status TEXT DEFAULT 'ACTIVE';
    """),
    ("0002_notifications_product_alert_column", """
        ALTER TABLE notifications ADD COLUMN product_alert_id INTEGER REFERENCES product_alerts (id);
    """),
    ("0003_installment_columns", """
        ALTER TABLE promotions ADD COLUMN installment_count INTEGER;
        ALTER TABLE promotions ADD COLUMN installment_price REAL;
        ALTER TABLE promotions ADD COLUMN installment_no_interest INTEGER;
        ALTER TABLE products ADD COLUMN last_installment_count INTEGER;
        ALTER TABLE products ADD COLUMN last_installment_price REAL;
        ALTER TABLE products ADD COLUMN last_installment_no_interest INTEGER;
    """),
    ("0004_single_product_image", """
        DELETE FROM product_images
        WHERE id IN (
            SELECT id
            FROM (
                SELECT pi.id,
                       ROW_NUMBER() OVER (
                           PARTITION BY pi.product_id
                           ORDER BY
                               CASE WHEN pi.image_url = p.image_url THEN 0
                                    WHEN pi.is_primary = 1 THEN 1 ELSE 2 END,
                               pi.id
                       ) AS position
                FROM product_images pi
                JOIN products p ON p.id = pi.product_id
            ) ranked
            WHERE position > 1
        );
        UPDATE product_images SET is_primary = 1;
        UPDATE products
        SET image_url = (
            SELECT image_url FROM product_images
            WHERE product_images.product_id = products.id
        )
        WHERE image_url IS NULL
          AND EXISTS (
              SELECT 1 FROM product_images
              WHERE product_images.product_id = products.id
          );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_product_images_one_per_product
            ON product_images (product_id);
    """),
]

_TRACKING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    id TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def apply_pending(conn: sqlite3.Connection, migrations: Optional[List[Migration]] = None) -> List[str]:
    """Aplica migrações pendentes de forma idempotente: cada migração roda no
    máximo uma vez, controlada pela tabela schema_migrations. Retorna os ids
    aplicados nesta chamada (lista vazia se já estava tudo em dia)."""
    migrations = MIGRATIONS if migrations is None else migrations
    conn.execute(_TRACKING_TABLE_SQL)
    already_applied = {
        row["id"] for row in conn.execute("SELECT id FROM schema_migrations").fetchall()
    }

    newly_applied = []
    for migration_id, sql in migrations:
        if migration_id in already_applied:
            continue
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_migrations (id) VALUES (?)", (migration_id,))
        newly_applied.append(migration_id)

    conn.commit()
    return newly_applied
