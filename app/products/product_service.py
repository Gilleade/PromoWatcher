import sqlite3
from typing import Optional, Tuple

from app.database import insert_product, touch_product_seen
from app.products.matcher import DECISION_AUTO_MATCH, DECISION_AUTO_NEW, MatchDecision, match_product
from app.products.spec_extractor import ExtractedSpecs, build_variant_key


def _build_canonical_title(specs: ExtractedSpecs) -> str:
    parts = []
    if specs.brand:
        parts.append(specs.brand.title())
    if specs.model:
        parts.append(specs.model.title())
    if specs.variant_label:
        parts.append(specs.variant_label)
    return " ".join(parts) if parts else "Produto não identificado"


def _create_product(conn: sqlite3.Connection, specs: ExtractedSpecs) -> int:
    variant_key = build_variant_key(specs.brand, specs.model, specs.storage_gb, specs.ram_gb)
    return insert_product(
        conn,
        canonical_title=_build_canonical_title(specs),
        variant_key=variant_key,
        category=specs.category,
        brand=specs.brand,
        model=specs.model,
        variant_label=specs.variant_label,
        storage_gb=specs.storage_gb,
        ram_gb=specs.ram_gb,
        release_year=specs.release_year,
    )


def get_or_create_product(conn: sqlite3.Connection, specs: ExtractedSpecs) -> Tuple[Optional[int], MatchDecision]:
    """Resolve o product_id para uma promoção com base nas specs extraídas.
    Retorna (product_id, decision). product_id é None quando a decisão é
    NEEDS_REVIEW — o chamador é responsável por registrar o item na fila de
    revisão (product_match_queue) nesse caso, sem produto ainda associado."""
    decision = match_product(conn, specs)

    if decision.decision == DECISION_AUTO_MATCH:
        touch_product_seen(conn, decision.product_id)
        return decision.product_id, decision

    if decision.decision == DECISION_AUTO_NEW:
        product_id = _create_product(conn, specs)
        decision.product_id = product_id
        return product_id, decision

    return None, decision
