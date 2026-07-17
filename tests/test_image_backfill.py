import asyncio
from types import SimpleNamespace

from app.database import insert_product, insert_promotion, insert_raw_message
from app.services.image_backfill import (
    backfill_product_images,
    list_image_backfill_candidates,
)


def _seed_product_message(
    conn, *, product_id: int, raw_id: int, message_id: int,
) -> int:
    promotion_id = insert_promotion(
        conn,
        raw_message_id=raw_id,
        title_guess="Produto histórico",
        price=100.0,
        dedupe_key=f"historico-{message_id}",
        status="APPROVED",
    )
    conn.execute(
        "UPDATE promotions SET product_id = ? WHERE id = ?",
        (product_id, promotion_id),
    )
    conn.commit()
    return promotion_id


class FakeTelegramClient:
    def __init__(self, photos_by_message):
        self.photos_by_message = photos_by_message
        self.downloads = []

    async def get_input_entity(self, chat_id):
        return chat_id

    async def get_messages(self, entity, *, ids):
        photo_id = self.photos_by_message.get(ids)
        if photo_id is None:
            return SimpleNamespace(id=ids, photo=None)
        return SimpleNamespace(id=ids, photo=SimpleNamespace(id=photo_id))

    async def download_media(self, message, *, file):
        with open(file, "wb") as image:
            image.write(b"telegram-photo")
        self.downloads.append((message.id, file))
        return file


def test_candidates_include_original_and_occurrence(db_conn):
    product_id = insert_product(
        db_conn,
        canonical_title="Produto histórico",
        variant_key="produto|historico",
    )
    original_raw_id = insert_raw_message(
        db_conn,
        telegram_message_id=10,
        chat_id=100,
        chat_title="Canal",
        sender_id=None,
        message_text="Oferta",
        message_date="2026-07-01T10:00:00",
    )
    promotion_id = _seed_product_message(
        db_conn,
        product_id=product_id,
        raw_id=original_raw_id,
        message_id=10,
    )
    occurrence_raw_id = insert_raw_message(
        db_conn,
        telegram_message_id=20,
        chat_id=200,
        chat_title="Outro canal",
        sender_id=None,
        message_text="Repostagem",
        message_date="2026-07-02T10:00:00",
    )
    db_conn.execute(
        """
        INSERT INTO promotion_occurrences
            (promotion_id, raw_message_id, chat_title, message_date)
        VALUES (?, ?, 'Outro canal', '2026-07-02T10:00:00')
        """,
        (promotion_id, occurrence_raw_id),
    )
    db_conn.commit()

    candidates = list_image_backfill_candidates(db_conn)

    assert [item.telegram_message_id for item in candidates] == [20, 10]


def test_backfill_tries_history_and_is_idempotent(db_conn, tmp_path):
    product_id = insert_product(
        db_conn,
        canonical_title="Produto histórico",
        variant_key="produto|historico",
    )
    original_raw_id = insert_raw_message(
        db_conn,
        telegram_message_id=10,
        chat_id=100,
        chat_title="Canal",
        sender_id=None,
        message_text="Oferta",
        message_date="2026-07-02T10:00:00",
    )
    promotion_id = _seed_product_message(
        db_conn,
        product_id=product_id,
        raw_id=original_raw_id,
        message_id=10,
    )
    occurrence_raw_id = insert_raw_message(
        db_conn,
        telegram_message_id=20,
        chat_id=100,
        chat_title="Canal",
        sender_id=None,
        message_text="Repostagem com foto",
        message_date="2026-07-01T10:00:00",
    )
    db_conn.execute(
        """
        INSERT INTO promotion_occurrences
            (promotion_id, raw_message_id, chat_title, message_date)
        VALUES (?, ?, 'Canal', '2026-07-01T10:00:00')
        """,
        (promotion_id, occurrence_raw_id),
    )
    db_conn.commit()
    client = FakeTelegramClient({20: 999})

    first = asyncio.run(
        backfill_product_images(
            db_conn, client=client, images_dir=str(tmp_path), timeout=1,
        )
    )
    second = asyncio.run(
        backfill_product_images(
            db_conn, client=client, images_dir=str(tmp_path), timeout=1,
        )
    )

    assert first.candidate_products == 1
    assert first.messages_checked == 2
    assert first.images_added == 1
    assert first.products_without_photo == 0
    assert first.failures == []
    assert second.candidate_products == 0
    assert second.images_added == 0
    assert len(client.downloads) == 1
    product = db_conn.execute(
        "SELECT image_url FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    assert product["image_url"] == "/media/100_20_999.jpg"
    image = db_conn.execute(
        "SELECT * FROM product_images WHERE product_id = ?", (product_id,)
    ).fetchone()
    assert image["is_primary"] == 1
    assert image["source"] == "TELEGRAM_MEDIA"
    historical = db_conn.execute(
        "SELECT has_media, media_type FROM raw_messages WHERE id = ?",
        (occurrence_raw_id,),
    ).fetchone()
    assert historical["has_media"] == 1
    assert historical["media_type"] == "photo"


def test_backfill_does_not_replace_existing_image(db_conn, tmp_path):
    product_id = insert_product(
        db_conn,
        canonical_title="Produto com imagem",
        variant_key="produto|com-imagem",
        image_url="/media/existente.jpg",
    )
    raw_id = insert_raw_message(
        db_conn,
        telegram_message_id=10,
        chat_id=100,
        chat_title="Canal",
        sender_id=None,
        message_text="Oferta",
        message_date="2026-07-01T10:00:00",
    )
    _seed_product_message(
        db_conn,
        product_id=product_id,
        raw_id=raw_id,
        message_id=10,
    )
    client = FakeTelegramClient({10: 999})

    report = asyncio.run(
        backfill_product_images(
            db_conn, client=client, images_dir=str(tmp_path), timeout=1,
        )
    )

    assert report.candidate_products == 0
    assert client.downloads == []
    product = db_conn.execute(
        "SELECT image_url FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    assert product["image_url"] == "/media/existente.jpg"
