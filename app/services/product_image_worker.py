import asyncio
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app.products.product_service import attach_product_image

JOB_PENDING = "PENDING"
JOB_PROCESSING = "PROCESSING"
JOB_RETRY = "RETRY"
JOB_WAITING = "WAITING_NEW_OCCURRENCE"
JOB_READY = "READY"

CANDIDATE_PENDING = "PENDING"
CANDIDATE_RETRY = "RETRY"
CANDIDATE_EXHAUSTED = "EXHAUSTED"
CANDIDATE_SUCCESS = "SUCCESS"

_RETRY_DELAYS = (60, 300, 1800, 21600, 86400)


@dataclass(frozen=True)
class ImageCandidate:
    id: int
    product_id: int
    raw_message_id: int
    chat_id: int
    telegram_message_id: int
    attempts: int


@dataclass(frozen=True)
class ImageWorkerResult:
    processed: bool
    product_id: Optional[int] = None
    status: Optional[str] = None


def enqueue_image_candidate(
    conn: sqlite3.Connection, *, product_id: int, raw_message_id: int,
) -> bool:
    """Agenda uma mensagem somente se o produto existe e ainda não tem imagem."""
    try:
        conn.execute("BEGIN IMMEDIATE")
        product = conn.execute(
            "SELECT image_url, status FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if product is None or product["status"] != "ACTIVE" or product["image_url"] is not None:
            conn.rollback()
            return False
        conn.execute(
            "INSERT OR IGNORE INTO product_image_jobs (product_id) VALUES (?)",
            (product_id,),
        )
        inserted = conn.execute(
            """
            INSERT OR IGNORE INTO product_image_candidates (product_id, raw_message_id)
            VALUES (?, ?)
            """,
            (product_id, raw_message_id),
        ).rowcount > 0
        if inserted:
            conn.execute(
                """
                UPDATE product_image_jobs
                SET status = 'PENDING', next_attempt_at = datetime('now'),
                    locked_at = NULL, last_error = NULL, updated_at = datetime('now')
                WHERE product_id = ? AND status != 'READY'
                """,
                (product_id,),
            )
        conn.commit()
        return inserted
    except Exception:
        conn.rollback()
        raise


def sync_missing_product_image_jobs(conn: sqlite3.Connection) -> int:
    """Recupera produtos sem imagem, inclusive após reinício ou match tardio."""
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE product_image_jobs
            SET status = 'READY', locked_at = NULL, last_error = NULL,
                updated_at = datetime('now')
            WHERE product_id IN (SELECT id FROM products WHERE image_url IS NOT NULL)
              AND status != 'READY'
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO product_image_jobs (product_id)
            SELECT id FROM products WHERE status = 'ACTIVE' AND image_url IS NULL
            """
        )
        before = conn.total_changes
        conn.execute(
            """
            INSERT OR IGNORE INTO product_image_candidates (product_id, raw_message_id)
            SELECT product_id, raw_message_id
            FROM (
                SELECT p.product_id, p.raw_message_id
                FROM promotions p
                WHERE p.product_id IS NOT NULL
                UNION
                SELECT p.product_id, o.raw_message_id
                FROM promotions p
                JOIN promotion_occurrences o ON o.promotion_id = p.id
                WHERE p.product_id IS NOT NULL
            ) candidates
            WHERE product_id IN (
                SELECT id FROM products WHERE status = 'ACTIVE' AND image_url IS NULL
            )
            """
        )
        inserted = conn.total_changes - before
        conn.execute(
            """
            UPDATE product_image_jobs
            SET status = 'PENDING', next_attempt_at = datetime('now'),
                locked_at = NULL, updated_at = datetime('now')
            WHERE status = 'WAITING_NEW_OCCURRENCE'
              AND EXISTS (
                  SELECT 1 FROM product_image_candidates c
                  WHERE c.product_id = product_image_jobs.product_id
                    AND c.status = 'PENDING'
              )
            """
        )
        conn.commit()
        return inserted
    except Exception:
        conn.rollback()
        raise


def _claim_next_job(conn: sqlite3.Connection) -> Optional[int]:
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE product_image_jobs
            SET status = 'RETRY', next_attempt_at = datetime('now'), locked_at = NULL,
                last_error = 'Tarefa recuperada após interrupção', updated_at = datetime('now')
            WHERE status = 'PROCESSING'
              AND locked_at < datetime('now', '-10 minutes')
            """
        )
        row = conn.execute(
            """
            SELECT j.product_id
            FROM product_image_jobs j
            JOIN products p ON p.id = j.product_id
            WHERE j.status IN ('PENDING', 'RETRY')
              AND j.next_attempt_at <= datetime('now')
              AND p.status = 'ACTIVE' AND p.image_url IS NULL
            ORDER BY j.next_attempt_at, j.created_at
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            conn.rollback()
            return None
        product_id = row["product_id"]
        conn.execute(
            """
            UPDATE product_image_jobs
            SET status = 'PROCESSING', attempts = attempts + 1,
                locked_at = datetime('now'), updated_at = datetime('now')
            WHERE product_id = ?
            """,
            (product_id,),
        )
        conn.commit()
        return product_id
    except Exception:
        conn.rollback()
        raise


def _next_candidate(conn: sqlite3.Connection, product_id: int) -> Optional[ImageCandidate]:
    row = conn.execute(
        """
        SELECT c.id, c.product_id, c.raw_message_id, c.attempts,
               r.chat_id, r.telegram_message_id
        FROM product_image_candidates c
        JOIN raw_messages r ON r.id = c.raw_message_id
        WHERE c.product_id = ? AND c.status IN ('PENDING', 'RETRY')
        ORDER BY CASE c.status WHEN 'RETRY' THEN 0 ELSE 1 END,
                 r.message_date DESC, c.id DESC
        LIMIT 1
        """,
        (product_id,),
    ).fetchone()
    return ImageCandidate(**dict(row)) if row is not None else None


def _mark_candidate_exhausted(
    conn: sqlite3.Connection, candidate_id: int, reason: str,
) -> None:
    conn.execute(
        """
        UPDATE product_image_candidates
        SET status = 'EXHAUSTED', attempts = attempts + 1,
            last_error = ?, tried_at = datetime('now')
        WHERE id = ?
        """,
        (reason[:500], candidate_id),
    )
    conn.commit()


def _schedule_retry(
    conn: sqlite3.Connection, *, product_id: int, candidate_id: int,
    attempts: int, error: str, delay_override: Optional[int] = None,
) -> None:
    delay = delay_override or _RETRY_DELAYS[min(attempts, len(_RETRY_DELAYS) - 1)]
    next_attempt = datetime.now(timezone.utc) + timedelta(seconds=delay)
    conn.execute(
        """
        UPDATE product_image_candidates
        SET status = 'RETRY', attempts = attempts + 1,
            last_error = ?, tried_at = datetime('now')
        WHERE id = ?
        """,
        (error[:500], candidate_id),
    )
    conn.execute(
        """
        UPDATE product_image_jobs
        SET status = 'RETRY', next_attempt_at = ?, locked_at = NULL,
            last_error = ?, updated_at = datetime('now')
        WHERE product_id = ?
        """,
        (next_attempt.strftime("%Y-%m-%d %H:%M:%S"), error[:500], product_id),
    )
    conn.commit()


def _mark_waiting(conn: sqlite3.Connection, product_id: int) -> None:
    conn.execute(
        """
        UPDATE product_image_jobs
        SET status = 'WAITING_NEW_OCCURRENCE', locked_at = NULL,
            last_error = 'Nenhuma ocorrência conhecida contém foto',
            updated_at = datetime('now')
        WHERE product_id = ?
        """,
        (product_id,),
    )
    conn.commit()


def _mark_ready(
    conn: sqlite3.Connection, *, product_id: int, candidate: ImageCandidate,
) -> None:
    conn.execute(
        """
        UPDATE product_image_candidates
        SET status = 'SUCCESS', attempts = attempts + 1,
            last_error = NULL, tried_at = datetime('now')
        WHERE id = ?
        """,
        (candidate.id,),
    )
    conn.execute(
        """
        UPDATE product_image_jobs
        SET status = 'READY', locked_at = NULL, last_error = NULL,
            updated_at = datetime('now')
        WHERE product_id = ?
        """,
        (product_id,),
    )
    conn.execute(
        """
        UPDATE raw_messages
        SET has_media = 1, media_type = COALESCE(media_type, 'photo')
        WHERE id = ?
        """,
        (candidate.raw_message_id,),
    )
    conn.commit()


async def _resolve_entity(client: Any, chat_id: int, cache: dict[int, Any]) -> Any:
    if chat_id in cache:
        return cache[chat_id]
    try:
        entity = await client.get_input_entity(chat_id)
    except Exception:
        entity = await client.get_entity(chat_id)
    cache[chat_id] = entity
    return entity


def _is_valid_image(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    with path.open("rb") as image_file:
        header = image_file.read(12)
    return (
        header.startswith(b"\xff\xd8\xff")
        or header.startswith(b"\x89PNG\r\n\x1a\n")
        or header.startswith((b"GIF87a", b"GIF89a"))
        or (header.startswith(b"RIFF") and header[8:12] == b"WEBP")
    )


async def process_product_image_job_once(
    conn: sqlite3.Connection,
    *,
    client: Any,
    images_dir: str,
    timeout: float,
    entity_cache: Optional[dict[int, Any]] = None,
) -> ImageWorkerResult:
    product_id = _claim_next_job(conn)
    if product_id is None:
        return ImageWorkerResult(processed=False)
    cache = entity_cache if entity_cache is not None else {}

    while True:
        product = conn.execute(
            "SELECT image_url FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if product is None or product["image_url"] is not None:
            conn.execute(
                "UPDATE product_image_jobs SET status = 'READY', locked_at = NULL WHERE product_id = ?",
                (product_id,),
            )
            conn.commit()
            return ImageWorkerResult(True, product_id, JOB_READY)

        candidate = _next_candidate(conn, product_id)
        if candidate is None:
            _mark_waiting(conn, product_id)
            return ImageWorkerResult(True, product_id, JOB_WAITING)

        final_path: Optional[Path] = None
        staging_path: Optional[Path] = None
        moved_to_final = False
        image_linked = False
        try:
            entity = await _resolve_entity(client, candidate.chat_id, cache)
            message = await client.get_messages(entity, ids=candidate.telegram_message_id)
            photo = getattr(message, "photo", None) if message is not None else None
            if message is None:
                _mark_candidate_exhausted(conn, candidate.id, "Mensagem não encontrada")
                continue
            if photo is None:
                _mark_candidate_exhausted(conn, candidate.id, "Mensagem sem foto")
                continue

            images_root = Path(images_dir)
            staging_root = images_root / ".staging"
            images_root.mkdir(parents=True, exist_ok=True)
            staging_root.mkdir(parents=True, exist_ok=True)
            filename = f"{candidate.chat_id}_{candidate.telegram_message_id}_{photo.id}.jpg"
            final_path = images_root / filename
            staging_path = staging_root / f"{filename}.part"

            if not _is_valid_image(final_path):
                if staging_path.exists():
                    staging_path.unlink()
                downloaded = await asyncio.wait_for(
                    client.download_media(message, file=str(staging_path)), timeout=timeout,
                )
                downloaded_path = Path(downloaded) if downloaded is not None else staging_path
                if downloaded_path != staging_path and downloaded_path.exists():
                    os.replace(downloaded_path, staging_path)
                if not _is_valid_image(staging_path):
                    raise RuntimeError("Telegram retornou um arquivo de imagem inválido")
                os.replace(staging_path, final_path)
                moved_to_final = True

            attached = attach_product_image(
                conn, product_id=product_id, local_path=str(final_path),
            )
            image_linked = attached
            if not attached:
                current = conn.execute(
                    "SELECT image_url FROM products WHERE id = ?", (product_id,)
                ).fetchone()
                current_name = Path(current["image_url"]).name if current and current["image_url"] else None
                if moved_to_final and current_name != final_path.name and final_path.exists():
                    final_path.unlink()
            _mark_ready(conn, product_id=product_id, candidate=candidate)
            return ImageWorkerResult(True, product_id, JOB_READY)
        except Exception as exc:
            if (
                moved_to_final and not image_linked
                and final_path is not None and final_path.exists()
            ):
                if staging_path is not None:
                    os.replace(final_path, staging_path)
            delay = getattr(exc, "seconds", None)
            _schedule_retry(
                conn,
                product_id=product_id,
                candidate_id=candidate.id,
                attempts=candidate.attempts,
                error=f"{type(exc).__name__}: {exc}",
                delay_override=int(delay) if delay else None,
            )
            return ImageWorkerResult(True, product_id, JOB_RETRY)


def cleanup_stale_staging_files(images_dir: str, *, max_age_hours: int = 24) -> int:
    staging_root = Path(images_dir) / ".staging"
    if not staging_root.is_dir():
        return 0
    cutoff = datetime.now().timestamp() - max_age_hours * 3600
    removed = 0
    for path in staging_root.glob("*.part"):
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    return removed


async def product_image_worker_loop(
    client: Any,
    get_conn: Callable[[], sqlite3.Connection],
    *,
    images_dir: str,
    timeout: float,
    poll_interval: float = 5.0,
) -> None:
    entity_cache: dict[int, Any] = {}
    cleanup_stale_staging_files(images_dir)
    while True:
        conn = get_conn()
        try:
            sync_missing_product_image_jobs(conn)
            result = await process_product_image_job_once(
                conn,
                client=client,
                images_dir=images_dir,
                timeout=timeout,
                entity_cache=entity_cache,
            )
        except Exception as exc:
            print(f"[media-worker] erro: {type(exc).__name__}: {exc}")
            result = ImageWorkerResult(processed=False)
        finally:
            conn.close()
        if not result.processed:
            await asyncio.sleep(poll_interval)
        else:
            await asyncio.sleep(0)
