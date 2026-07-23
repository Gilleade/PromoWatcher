import asyncio
import os
import sqlite3
from dataclasses import dataclass, field
from itertools import groupby
from typing import Any, Optional


@dataclass(frozen=True)
class ImageBackfillCandidate:
    product_id: int
    raw_message_id: int
    chat_id: int
    telegram_message_id: int
    message_date: Optional[str]


@dataclass
class ImageBackfillReport:
    candidate_products: int = 0
    messages_checked: int = 0
    images_added: int = 0
    products_without_photo: int = 0
    failures: list[str] = field(default_factory=list)


def list_image_backfill_candidates(conn: sqlite3.Connection) -> list[ImageBackfillCandidate]:
    """Lista mensagens históricas de produtos ativos ainda sem imagem.

    Além da mensagem que criou a promoção, inclui ocorrências posteriores:
    uma repostagem pode conter foto mesmo quando a publicação original não
    continha. O UNION evita consultar duas vezes a mesma mensagem.
    """
    rows = conn.execute(
        """
        WITH candidate_messages AS (
            SELECT p.product_id, r.id AS raw_message_id, r.chat_id,
                   r.telegram_message_id, r.message_date
            FROM promotions p
            JOIN raw_messages r ON r.id = p.raw_message_id
            WHERE p.product_id IS NOT NULL

            UNION

            SELECT p.product_id, r.id AS raw_message_id, r.chat_id,
                   r.telegram_message_id, r.message_date
            FROM promotions p
            JOIN promotion_occurrences o ON o.promotion_id = p.id
            JOIN raw_messages r ON r.id = o.raw_message_id
            WHERE p.product_id IS NOT NULL
        )
        SELECT cm.product_id, cm.raw_message_id, cm.chat_id,
               cm.telegram_message_id, cm.message_date
        FROM candidate_messages cm
        JOIN products p ON p.id = cm.product_id
        WHERE p.status = 'ACTIVE' AND p.image_url IS NULL
        ORDER BY cm.product_id, cm.message_date DESC, cm.raw_message_id DESC
        """
    ).fetchall()
    return [
        ImageBackfillCandidate(
            product_id=row["product_id"],
            raw_message_id=row["raw_message_id"],
            chat_id=row["chat_id"],
            telegram_message_id=row["telegram_message_id"],
            message_date=row["message_date"],
        )
        for row in rows
    ]


def _attach_backfilled_image(
    conn: sqlite3.Connection, *, candidate: ImageBackfillCandidate, local_path: str,
) -> bool:
    """Vincula a imagem e corrige o metadado histórico em uma transação.

    O UPDATE condicional torna a operação idempotente e impede que o
    retropreenchimento substitua uma imagem adicionada pelo watcher.
    """
    filename = os.path.basename(local_path)
    image_url = f"/media/{filename}"
    try:
        conn.execute("BEGIN IMMEDIATE")
        updated = conn.execute(
            """
            UPDATE products
            SET image_url = ?, updated_at = datetime('now')
            WHERE id = ? AND status = 'ACTIVE' AND image_url IS NULL
            """,
            (image_url, candidate.product_id),
        )
        if updated.rowcount == 0:
            conn.rollback()
            return False
        conn.execute(
            """
            INSERT INTO product_images
                (product_id, image_url, local_path, source, is_primary)
            VALUES (?, ?, ?, 'TELEGRAM_MEDIA', 1)
            """,
            (candidate.product_id, image_url, local_path),
        )
        conn.execute(
            """
            UPDATE raw_messages
            SET has_media = 1, media_type = COALESCE(media_type, 'photo')
            WHERE chat_id = ? AND telegram_message_id = ?
            """,
            (candidate.chat_id, candidate.telegram_message_id),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


async def _resolve_entity(client: Any, chat_id: int) -> Any:
    try:
        return await client.get_input_entity(chat_id)
    except Exception:
        return await client.get_entity(chat_id)


async def backfill_product_images(
    conn: sqlite3.Connection,
    *,
    client: Any,
    images_dir: str,
    timeout: float,
    product_limit: Optional[int] = None,
) -> ImageBackfillReport:
    """Busca no Telegram a primeira foto disponível de cada produto sem imagem."""
    candidates = list_image_backfill_candidates(conn)
    grouped = groupby(candidates, key=lambda candidate: candidate.product_id)
    product_candidates = [(product_id, list(items)) for product_id, items in grouped]
    if product_limit is not None:
        product_candidates = product_candidates[:product_limit]

    report = ImageBackfillReport(candidate_products=len(product_candidates))
    entity_cache: dict[int, Any] = {}
    os.makedirs(images_dir, exist_ok=True)

    for product_id, messages in product_candidates:
        attached = False
        for candidate in messages:
            report.messages_checked += 1
            try:
                if candidate.chat_id not in entity_cache:
                    entity_cache[candidate.chat_id] = await _resolve_entity(
                        client, candidate.chat_id,
                    )
                entity = entity_cache[candidate.chat_id]
                message = await client.get_messages(
                    entity, ids=candidate.telegram_message_id,
                )
                photo = getattr(message, "photo", None) if message is not None else None
                if photo is None:
                    continue

                filename = (
                    f"{candidate.chat_id}_{candidate.telegram_message_id}_{photo.id}.jpg"
                )
                local_path = os.path.join(images_dir, filename)
                if not os.path.isfile(local_path) or os.path.getsize(local_path) == 0:
                    downloaded_path = await asyncio.wait_for(
                        client.download_media(message, file=local_path),
                        timeout=timeout,
                    )
                    if downloaded_path is None:
                        raise RuntimeError("Telegram não retornou um arquivo para a foto")
                    local_path = str(downloaded_path)
                if not os.path.isfile(local_path) or os.path.getsize(local_path) == 0:
                    raise RuntimeError("arquivo de imagem ausente ou vazio após o download")

                if _attach_backfilled_image(
                    conn, candidate=candidate, local_path=local_path,
                ):
                    report.images_added += 1
                attached = True
                break
            except Exception as exc:
                report.failures.append(
                    f"produto {product_id}, chat {candidate.chat_id}, "
                    f"mensagem {candidate.telegram_message_id}: "
                    f"{type(exc).__name__}: {exc}"
                )

        if not attached:
            report.products_without_photo += 1

    return report
