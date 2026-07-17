from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.database import get_connection, init_db
from app.services.message_processor import process


def test_concurrent_messages_create_one_promotion_and_one_product(tmp_path):
    db_path = str(tmp_path / "concurrent_pipeline.sqlite3")
    setup = init_db(db_path)
    setup.close()
    barrier = Barrier(2)
    message = "Notebook Dell Inspiron 15 8GB RAM 256GB SSD por R$ 2.999,00"

    def run(message_id):
        conn = get_connection(db_path)
        try:
            barrier.wait()
            return process(
                conn,
                telegram_message_id=message_id,
                chat_id=message_id,
                chat_title=f"Grupo {message_id}",
                sender_id=None,
                message_text=message,
                message_date="2026-07-16T10:00:00",
                alerts=[],
            )
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, (1, 2)))

    assert sorted(result.status for result in results) == ["DUPLICATE", "NEW_IGNORED"]
    verify = get_connection(db_path)
    assert verify.execute("SELECT COUNT(*) FROM promotions").fetchone()[0] == 1
    assert verify.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
    assert verify.execute("SELECT COUNT(*) FROM promotion_occurrences").fetchone()[0] == 1
    assert verify.execute("SELECT COUNT(*) FROM product_price_history").fetchone()[0] == 1
    verify.close()
