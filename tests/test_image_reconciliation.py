from pathlib import Path

from app.database import insert_product
from app.products.product_service import attach_product_image
from app.services.image_reconciliation import (
    inspect_product_images,
    quarantine_orphan_images,
)


def test_reconciliation_identifies_and_quarantines_only_orphans(db_conn, tmp_path):
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    valid = images_dir / "valid.jpg"
    orphan = images_dir / "orphan.jpg"
    valid.write_bytes(b"valid")
    orphan.write_bytes(b"orphan")
    product_id = insert_product(
        db_conn, canonical_title="Produto", variant_key="produto|1",
    )
    attach_product_image(db_conn, product_id=product_id, local_path=str(valid))

    report = inspect_product_images(db_conn, images_dir=str(images_dir))

    assert report.referenced_files == 1
    assert report.orphan_files == (orphan,)
    assert report.missing_references == ()

    quarantine = tmp_path / "quarantine"
    moved = quarantine_orphan_images(
        db_conn, images_dir=str(images_dir), quarantine_dir=str(quarantine),
    )
    assert moved.orphan_files == (orphan,)
    assert valid.exists()
    assert not orphan.exists()
    assert (quarantine / "orphan.jpg").read_bytes() == b"orphan"


def test_reconciliation_reports_missing_referenced_file(db_conn, tmp_path):
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    product_id = insert_product(
        db_conn,
        canonical_title="Produto",
        variant_key="produto|1",
        image_url="/media/missing.jpg",
    )
    assert product_id is not None

    report = inspect_product_images(db_conn, images_dir=str(images_dir))

    assert report.missing_references == ("missing.jpg",)


def test_reconciliation_ignores_staging_subdirectory(db_conn, tmp_path):
    images_dir = tmp_path / "images"
    staging = images_dir / ".staging"
    staging.mkdir(parents=True)
    (staging / "download.part").write_bytes(b"partial")

    report = inspect_product_images(db_conn, images_dir=str(images_dir))

    assert report.orphan_files == ()
