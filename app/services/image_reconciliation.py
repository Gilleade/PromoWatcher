import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImageReconciliationReport:
    referenced_files: int
    orphan_files: tuple[Path, ...]
    orphan_bytes: int
    missing_references: tuple[str, ...]


def inspect_product_images(
    conn: sqlite3.Connection, *, images_dir: str,
) -> ImageReconciliationReport:
    images_root = Path(images_dir).resolve()
    references = {
        Path(row[0]).name
        for row in conn.execute(
            """
            SELECT image_url FROM products WHERE image_url IS NOT NULL
            UNION
            SELECT image_url FROM product_images WHERE image_url IS NOT NULL
            UNION
            SELECT local_path FROM product_images WHERE local_path IS NOT NULL
            """
        )
        if row[0]
    }
    files = tuple(
        path for path in images_root.iterdir()
        if path.is_file()
    ) if images_root.is_dir() else ()
    by_name = {path.name: path for path in files}
    orphans = tuple(sorted(
        (path for path in files if path.name not in references),
        key=lambda path: path.name,
    ))
    missing = tuple(sorted(name for name in references if name not in by_name))
    return ImageReconciliationReport(
        referenced_files=len(references),
        orphan_files=orphans,
        orphan_bytes=sum(path.stat().st_size for path in orphans),
        missing_references=missing,
    )


def quarantine_orphan_images(
    conn: sqlite3.Connection,
    *,
    images_dir: str,
    quarantine_dir: str,
) -> ImageReconciliationReport:
    """Move apenas arquivos sem qualquer referência, preservando-os para rollback."""
    report = inspect_product_images(conn, images_dir=images_dir)
    if not report.orphan_files:
        return report

    images_root = Path(images_dir).resolve()
    quarantine_root = Path(quarantine_dir).resolve()
    quarantine_root.mkdir(parents=True, exist_ok=True)
    destinations = {source: quarantine_root / source.name for source in report.orphan_files}
    for source, destination in destinations.items():
        resolved_source = source.resolve()
        if resolved_source.parent != images_root:
            raise ValueError(f"Arquivo fora do diretório de imagens: {resolved_source}")
        if destination.exists():
            raise FileExistsError(f"Destino de quarentena já existe: {destination}")
    for source in report.orphan_files:
        os.replace(source.resolve(), destinations[source])
    return report
