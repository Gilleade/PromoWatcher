"""Retropreenche imagens dos produtos registrados antes da captura de mídia.

Uso recomendado com o watcher parado para evitar duas conexões simultâneas
usando a mesma sessão do Telegram:

    python backfill_product_images.py --dry-run
    python backfill_product_images.py
"""
import argparse
import asyncio
from dataclasses import replace

from app.config import get_config
from app.database import get_connection, init_db
from app.services.image_backfill import (
    backfill_product_images,
    list_image_backfill_candidates,
)
from app.telegram_client import create_client


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Busca no Telegram imagens de produtos históricos ainda sem foto.",
    )
    parser.add_argument("--dry-run", action="store_true", help="apenas informa os candidatos")
    parser.add_argument("--limit", type=int, help="limita a quantidade de produtos processados")
    parser.add_argument("--db-path", help="sobrescreve DB_PATH")
    parser.add_argument("--images-dir", help="sobrescreve IMAGES_DIR")
    parser.add_argument("--session-name", help="sobrescreve SESSION_NAME")
    return parser


async def _run(args: argparse.Namespace) -> int:
    config = get_config()
    config = replace(
        config,
        db_path=args.db_path or config.db_path,
        images_dir=args.images_dir or config.images_dir,
        session_name=args.session_name or config.session_name,
    )

    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit deve ser maior que zero")

    if args.dry_run:
        conn = get_connection(config.db_path)
        try:
            candidates = list_image_backfill_candidates(conn)
            product_ids = list(dict.fromkeys(item.product_id for item in candidates))
            if args.limit is not None:
                product_ids = product_ids[:args.limit]
            print(f"Produtos sem imagem com mensagens históricas: {len(product_ids)}")
            print(f"Mensagens disponíveis para consulta: {len(candidates)}")
            return 0
        finally:
            conn.close()

    conn = init_db(config.db_path)
    client = create_client(config)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError(
                "A sessão do Telegram não está autenticada. Inicie o watcher e autentique-a antes."
            )
        report = await backfill_product_images(
            conn,
            client=client,
            images_dir=config.images_dir,
            timeout=config.media_download_timeout,
            product_limit=args.limit,
        )
    finally:
        await client.disconnect()
        conn.close()

    print(f"Produtos candidatos: {report.candidate_products}")
    print(f"Mensagens consultadas: {report.messages_checked}")
    print(f"Imagens adicionadas: {report.images_added}")
    print(f"Produtos sem foto disponível: {report.products_without_photo}")
    if report.failures:
        print(f"Falhas pontuais: {len(report.failures)}")
        for failure in report.failures:
            print(f"- {failure}")
    return 1 if report.failures else 0


def main() -> int:
    args = _build_parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
