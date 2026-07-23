import asyncio
from types import SimpleNamespace

from app.database import insert_product, insert_promotion, insert_raw_message
from app.products.catalog_service import list_feed_products
from app.services.product_image_worker import (
    JOB_READY,
    JOB_RETRY,
    enqueue_image_candidate,
    process_product_image_job_once,
    sync_missing_product_image_jobs,
)


def _raw(conn, *, message_id: int, date: str, has_media: bool = True) -> int:
    return insert_raw_message(
        conn,
        telegram_message_id=message_id,
        chat_id=100,
        chat_title="Canal",
        sender_id=None,
        message_text="Produto por R$ 100",
        message_date=date,
        has_media=has_media,
    )


def _promotion(conn, *, product_id: int, raw_message_id: int) -> int:
    promotion_id = insert_promotion(
        conn,
        raw_message_id=raw_message_id,
        price=100,
        status="APPROVED",
        dedupe_key=f"produto-{raw_message_id}",
    )
    conn.execute(
        "UPDATE promotions SET product_id = ? WHERE id = ?",
        (product_id, promotion_id),
    )
    conn.commit()
    return promotion_id


class FakeTelegramClient:
    def __init__(self, photos=None, errors=None):
        self.photos = photos or {}
        self.errors = errors or {}
        self.downloads = []

    async def get_input_entity(self, chat_id):
        return chat_id

    async def get_messages(self, entity, *, ids):
        if ids in self.errors:
            raise self.errors[ids]
        photo_id = self.photos.get(ids)
        return SimpleNamespace(
            id=ids,
            photo=SimpleNamespace(id=photo_id) if photo_id is not None else None,
        )

    async def download_media(self, message, *, file):
        with open(file, "wb") as image:
            image.write(b"\xff\xd8\xff\xe0telegram-photo")
        self.downloads.append((message.id, file))
        return file


def test_enqueue_requires_an_existing_product_without_image(db_conn):
    raw_id = _raw(db_conn, message_id=1, date="2026-07-17T10:00:00")
    product_id = insert_product(
        db_conn, canonical_title="Produto", variant_key="produto|1",
    )

    first = enqueue_image_candidate(
        db_conn, product_id=product_id, raw_message_id=raw_id,
    )
    duplicate = enqueue_image_candidate(
        db_conn, product_id=product_id, raw_message_id=raw_id,
    )

    assert first is True
    assert duplicate is False
    assert db_conn.execute("SELECT COUNT(*) FROM product_image_jobs").fetchone()[0] == 1
    assert db_conn.execute("SELECT COUNT(*) FROM product_image_candidates").fetchone()[0] == 1


def test_sync_recovers_original_message_and_occurrence(db_conn):
    product_id = insert_product(
        db_conn, canonical_title="Produto", variant_key="produto|1",
    )
    original_raw = _raw(db_conn, message_id=1, date="2026-07-17T10:00:00")
    promotion_id = _promotion(
        db_conn, product_id=product_id, raw_message_id=original_raw,
    )
    occurrence_raw = _raw(db_conn, message_id=2, date="2026-07-17T11:00:00")
    db_conn.execute(
        """
        INSERT INTO promotion_occurrences
            (promotion_id, raw_message_id, chat_title, message_date)
        VALUES (?, ?, 'Canal', '2026-07-17T11:00:00')
        """,
        (promotion_id, occurrence_raw),
    )
    db_conn.commit()

    inserted = sync_missing_product_image_jobs(db_conn)

    assert inserted == 2
    assert db_conn.execute("SELECT COUNT(*) FROM product_image_jobs").fetchone()[0] == 1
    assert db_conn.execute("SELECT COUNT(*) FROM product_image_candidates").fetchone()[0] == 2


def test_worker_tries_next_occurrence_and_registers_one_image(db_conn, tmp_path):
    product_id = insert_product(
        db_conn, canonical_title="Produto", variant_key="produto|1",
    )
    older_raw = _raw(db_conn, message_id=1, date="2026-07-17T10:00:00")
    promotion_id = _promotion(db_conn, product_id=product_id, raw_message_id=older_raw)
    newer_raw = _raw(db_conn, message_id=2, date="2026-07-17T11:00:00")
    db_conn.execute(
        """
        INSERT INTO promotion_occurrences
            (promotion_id, raw_message_id, chat_title, message_date)
        VALUES (?, ?, 'Canal', '2026-07-17T11:00:00')
        """,
        (promotion_id, newer_raw),
    )
    db_conn.commit()
    sync_missing_product_image_jobs(db_conn)
    client = FakeTelegramClient(photos={1: 999})

    result = asyncio.run(
        process_product_image_job_once(
            db_conn, client=client, images_dir=str(tmp_path), timeout=1,
        )
    )

    assert result.status == JOB_READY
    assert [download[0] for download in client.downloads] == [1]
    product = db_conn.execute(
        "SELECT image_url FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    assert product["image_url"] == "/media/100_1_999.jpg"
    assert db_conn.execute(
        "SELECT COUNT(*) FROM product_images WHERE product_id = ?", (product_id,)
    ).fetchone()[0] == 1
    statuses = {
        row["raw_message_id"]: row["status"]
        for row in db_conn.execute("SELECT raw_message_id, status FROM product_image_candidates")
    }
    assert statuses == {newer_raw: "EXHAUSTED", older_raw: "SUCCESS"}


def test_worker_persists_transient_failure_for_retry(db_conn, tmp_path):
    product_id = insert_product(
        db_conn, canonical_title="Produto", variant_key="produto|1",
    )
    raw_id = _raw(db_conn, message_id=1, date="2026-07-17T10:00:00")
    _promotion(db_conn, product_id=product_id, raw_message_id=raw_id)
    sync_missing_product_image_jobs(db_conn)

    failed = asyncio.run(
        process_product_image_job_once(
            db_conn,
            client=FakeTelegramClient(errors={1: TimeoutError("temporário")}),
            images_dir=str(tmp_path),
            timeout=1,
        )
    )

    assert failed.status == JOB_RETRY
    job = db_conn.execute(
        "SELECT status, attempts, last_error FROM product_image_jobs WHERE product_id = ?",
        (product_id,),
    ).fetchone()
    assert job["status"] == JOB_RETRY
    assert job["attempts"] == 1
    assert "TimeoutError" in job["last_error"]

    db_conn.execute(
        "UPDATE product_image_jobs SET next_attempt_at = datetime('now') WHERE product_id = ?",
        (product_id,),
    )
    db_conn.commit()
    recovered = asyncio.run(
        process_product_image_job_once(
            db_conn,
            client=FakeTelegramClient(photos={1: 999}),
            images_dir=str(tmp_path),
            timeout=1,
        )
    )
    assert recovered.status == JOB_READY


def test_product_without_image_is_not_published_in_feed(db_conn):
    hidden_id = insert_product(
        db_conn, canonical_title="Sem imagem", variant_key="sem|imagem",
    )
    visible_id = insert_product(
        db_conn,
        canonical_title="Com imagem",
        variant_key="com|imagem",
        image_url="/media/produto.jpg",
    )

    rows = list_feed_products(db_conn)

    assert [row["id"] for row in rows] == [visible_id]
    assert hidden_id not in [row["id"] for row in rows]


def test_product_with_image_is_never_queued(db_conn):
    product_id = insert_product(
        db_conn,
        canonical_title="Com imagem",
        variant_key="com|imagem",
        image_url="/media/produto.jpg",
    )
    raw_id = _raw(db_conn, message_id=1, date="2026-07-17T10:00:00")
    _promotion(db_conn, product_id=product_id, raw_message_id=raw_id)

    inserted = sync_missing_product_image_jobs(db_conn)

    assert inserted == 0
    assert db_conn.execute("SELECT COUNT(*) FROM product_image_jobs").fetchone()[0] == 0
