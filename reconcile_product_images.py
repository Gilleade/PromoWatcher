"""Audita e, mediante --apply, coloca imagens órfãs em quarentena."""
import argparse
from datetime import datetime
from pathlib import Path

from app.config import get_config
from app.database import get_connection, init_db
from app.services.image_reconciliation import (
    inspect_product_images,
    quarantine_orphan_images,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="move os órfãos para quarentena")
    parser.add_argument("--db-path", help="sobrescreve DB_PATH")
    parser.add_argument("--images-dir", help="sobrescreve IMAGES_DIR")
    parser.add_argument("--quarantine-dir", help="diretório de destino da quarentena")
    return parser


def main() -> int:
    args = _parser().parse_args()
    config = get_config()
    db_path = args.db_path or config.db_path
    images_dir = args.images_dir or config.images_dir
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    quarantine_dir = args.quarantine_dir or str(
        Path(images_dir).parent / "images_quarantine" / stamp
    )

    conn = init_db(db_path) if args.apply else get_connection(db_path)
    try:
        if args.apply:
            report = quarantine_orphan_images(
                conn, images_dir=images_dir, quarantine_dir=quarantine_dir,
            )
        else:
            report = inspect_product_images(conn, images_dir=images_dir)
    finally:
        conn.close()

    print(f"Imagens referenciadas: {report.referenced_files}")
    print(f"Arquivos órfãos: {len(report.orphan_files)}")
    print(f"Bytes órfãos: {report.orphan_bytes}")
    print(f"Referências sem arquivo: {len(report.missing_references)}")
    if args.apply and report.orphan_files:
        print(f"Quarentena: {quarantine_dir}")
    return 1 if report.missing_references else 0


if __name__ == "__main__":
    raise SystemExit(main())
