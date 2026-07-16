import sqlite3
from dataclasses import dataclass
from typing import Optional, Tuple

from app.database import (
    insert_price_history_point,
    insert_product,
    list_price_history,
    touch_product_seen,
    update_product_price_stats,
)
from app.products.matcher import DECISION_AUTO_MATCH, DECISION_AUTO_NEW, MatchDecision, match_product
from app.products.spec_extractor import ExtractedSpecs, build_variant_key

# Mínimo de pontos de histórico antes de a detecção de bug por desvio entrar
# em ação — sem isso, os primeiros preços de um produto novo (sem "média"
# de verdade ainda) disparariam falso positivo.
MIN_HISTORY_POINTS_FOR_BUG_DETECTION = 5
BUG_DEVIATION_PERCENT_THRESHOLD = 40.0


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


def evaluate_bug_by_deviation(conn: sqlite3.Connection, product_id: int,
                               price: float) -> Tuple[bool, Optional[float]]:
    """Compara o preço atual com a média do histórico já registrado (sem
    contar o preço atual). Só ativa com histórico mínimo — um produto novo
    não tem "média" de verdade ainda. deviation_percent positivo = preço
    abaixo da média (quanto maior, melhor a oferta / mais suspeito de bug)."""
    history = list_price_history(conn, product_id)
    if len(history) < MIN_HISTORY_POINTS_FOR_BUG_DETECTION:
        return False, None

    prices = [row["price"] for row in history]
    mean = sum(prices) / len(prices)
    if mean <= 0:
        return False, None

    deviation_percent = ((mean - price) / mean) * 100
    is_bug = deviation_percent >= BUG_DEVIATION_PERCENT_THRESHOLD
    return is_bug, deviation_percent


@dataclass
class PricePointResult:
    price_history_id: int
    is_bug_candidate: bool
    deviation_percent: Optional[float]


def record_price_point(conn: sqlite3.Connection, *, product_id: int, price: float,
                        promotion_id: Optional[int] = None, old_price: Optional[float] = None,
                        coupon: Optional[str] = None, store_domain: Optional[str] = None,
                        source_chat_title: Optional[str] = None) -> PricePointResult:
    is_bug, deviation_percent = evaluate_bug_by_deviation(conn, product_id, price)

    price_history_id = insert_price_history_point(
        conn,
        product_id=product_id,
        promotion_id=promotion_id,
        price=price,
        old_price=old_price,
        coupon=coupon,
        store_domain=store_domain,
        source_chat_title=source_chat_title,
        is_bug_candidate=is_bug,
        deviation_percent=deviation_percent,
    )
    update_product_price_stats(conn, product_id, price)

    return PricePointResult(
        price_history_id=price_history_id, is_bug_candidate=is_bug, deviation_percent=deviation_percent,
    )
