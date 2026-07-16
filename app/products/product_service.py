import json
import sqlite3
from dataclasses import dataclass
from typing import Optional, Tuple

from app.database import (
    delete_favorite,
    get_match_queue_item,
    insert_favorite,
    insert_price_history_point,
    insert_product,
    insert_product_merge_record,
    list_price_history,
    reassign_price_history_to_product,
    reassign_promotions_to_product,
    set_product_merged,
    touch_product_seen,
    update_match_queue_status,
    update_product_price_stats,
    update_product_status,
    update_promotion_product_match,
    upsert_product_alert,
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
                        source_chat_title: Optional[str] = None,
                        installment_count: Optional[int] = None,
                        installment_price: Optional[float] = None,
                        installment_no_interest: Optional[bool] = None) -> PricePointResult:
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
    update_product_price_stats(
        conn, product_id, price,
        installment_count=installment_count,
        installment_price=installment_price,
        installment_no_interest=installment_no_interest,
    )

    return PricePointResult(
        price_history_id=price_history_id, is_bug_candidate=is_bug, deviation_percent=deviation_percent,
    )


def toggle_favorite(conn: sqlite3.Connection, product_id: int, favorited: bool) -> None:
    if favorited:
        insert_favorite(conn, product_id)
    else:
        delete_favorite(conn, product_id)


def set_product_blocked(conn: sqlite3.Connection, product_id: int, blocked: bool) -> None:
    """Bloquear tira o produto do feed/listagens (não lista mais, não
    registra mais histórico — ver requisito 9); desbloquear reativa."""
    update_product_status(conn, product_id, "BLOCKED" if blocked else "ACTIVE")


def set_product_alert(conn: sqlite3.Connection, product_id: int, *, enabled: bool,
                       max_price: Optional[float] = None, send_to_telegram: bool = True) -> int:
    return upsert_product_alert(
        conn, product_id=product_id, enabled=enabled, max_price=max_price,
        send_to_telegram=send_to_telegram,
    )


def merge_products(conn: sqlite3.Connection, *, source_product_id: int, target_product_id: int,
                    reason: Optional[str] = None) -> None:
    """Move o histórico de preço e as promoções do produto de origem para o
    de destino, marca a origem como MERGED (nunca apaga — preserva o
    histórico) e registra a auditoria em product_merges."""
    if source_product_id == target_product_id:
        raise ValueError("Não é possível mesclar um produto com ele mesmo.")
    reassign_promotions_to_product(conn, source_product_id=source_product_id, target_product_id=target_product_id)
    reassign_price_history_to_product(conn, source_product_id=source_product_id, target_product_id=target_product_id)
    set_product_merged(conn, source_product_id=source_product_id, target_product_id=target_product_id)
    insert_product_merge_record(
        conn, source_product_id=source_product_id, target_product_id=target_product_id, reason=reason,
    )


def resolve_match_queue_item_manually(conn: sqlite3.Connection, item_id: int, *, action: str,
                                       product_id: Optional[int] = None) -> dict:
    """Resolução manual de um item da fila de revisão (admin), alternativa
    ao Ollama quando ninguém decidiu automaticamente. action: 'assign' (usa
    o product_id informado), 'create_new' (cria produto a partir das specs
    já extraídas deterministicamente), 'ignore' (encerra sem produto)."""
    item = get_match_queue_item(conn, item_id)
    if item is None:
        raise ValueError(f"Item {item_id} não encontrado na fila.")

    specs = json.loads(item["extracted_specs_json"])

    if action == "assign":
        if product_id is None:
            raise ValueError("action='assign' exige product_id.")
        touch_product_seen(conn, product_id)
        update_promotion_product_match(
            conn, promotion_id=item["promotion_id"], product_id=product_id,
            match_status="MANUAL_MATCH", confidence=1.0,
        )
    elif action == "create_new":
        product_id = insert_product(
            conn,
            canonical_title=_build_canonical_title(ExtractedSpecs(
                brand=specs.get("brand"), model=specs.get("model"),
                storage_gb=specs.get("storage_gb"), ram_gb=specs.get("ram_gb"),
                release_year=specs.get("release_year"), category=specs.get("category"),
            )),
            variant_key=build_variant_key(
                specs.get("brand"), specs.get("model"), specs.get("storage_gb"), specs.get("ram_gb"),
            ),
            category=specs.get("category"), brand=specs.get("brand"), model=specs.get("model"),
            storage_gb=specs.get("storage_gb"), ram_gb=specs.get("ram_gb"),
            release_year=specs.get("release_year"),
        )
        update_promotion_product_match(
            conn, promotion_id=item["promotion_id"], product_id=product_id,
            match_status="MANUAL_NEW", confidence=1.0,
        )
    elif action == "ignore":
        product_id = None
        update_promotion_product_match(
            conn, promotion_id=item["promotion_id"], product_id=None,
            match_status="IGNORED_MANUAL", confidence=0.0,
        )
    else:
        raise ValueError(f"action inválida: {action!r} (use 'assign', 'create_new' ou 'ignore').")

    update_match_queue_status(
        conn, item_id, status="DONE", attempts=item["attempts"] + 1,
        result_json=json.dumps({"action": action, "product_id": product_id}),
    )
    return {"action": action, "product_id": product_id}
