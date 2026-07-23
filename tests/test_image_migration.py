import sqlite3

import pytest

from app.database import get_connection
from app.migrations import MIGRATIONS, apply_pending


def test_single_image_migration_keeps_current_product_image():
    conn = get_connection(":memory:")
    conn.executescript("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            image_url TEXT
        );
        CREATE TABLE product_images (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            image_url TEXT,
            is_primary INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO products (id, image_url) VALUES (1, '/media/current.jpg');
        INSERT INTO product_images VALUES (1, 1, '/media/old.jpg', 1);
        INSERT INTO product_images VALUES (2, 1, '/media/current.jpg', 0);
    """)
    migration_sql = dict(MIGRATIONS)["0004_single_product_image"]

    applied = apply_pending(
        conn, [("0004_single_product_image", migration_sql)],
    )

    assert applied == ["0004_single_product_image"]
    rows = conn.execute("SELECT image_url, is_primary FROM product_images").fetchall()
    assert [(row["image_url"], row["is_primary"]) for row in rows] == [
        ("/media/current.jpg", 1),
    ]
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO product_images VALUES (3, 1, '/media/other.jpg', 0)"
        )
    conn.close()
