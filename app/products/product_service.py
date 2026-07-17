import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Optional, Tuple

from app.database import (
    delete_favorite,
    get_match_queue_item,
    insert_favorite,
    insert_price_history_point,
    insert_product,
    insert_product_image,
    list_price_history,
    touch_product_seen,
    update_match_queue_status,
    update_product_image_url_if_null,
    update_product_price_stats,
    update_product_status,
    update_promotion_product_match,
    upsert_product_alert,
)
from app.products.matcher import (
    DECISION_AUTO_MATCH,
    DECISION_AUTO_NEW,
    DECISION_BLOCKED,
    MatchDecision,
    match_product,
)
from app.products.spec_extractor import CATEGORY_TITLE_PREFIX, ExtractedSpecs, build_variant_key

# Mínimo de pontos de histórico antes de a detecção de bug por desvio entrar
# em ação — sem isso, os primeiros preços de um produto novo (sem "média"
# de verdade ainda) disparariam falso positivo.
MIN_HISTORY_POINTS_FOR_BUG_DETECTION = 5
BUG_DEVIATION_PERCENT_THRESHOLD = 40.0


def _build_canonical_title(specs: ExtractedSpecs) -> str:
    parts = []
    if specs.category and specs.category in CATEGORY_TITLE_PREFIX:
        parts.append(CATEGORY_TITLE_PREFIX[specs.category])
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

    if decision.decision == DECISION_BLOCKED:
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


def attach_product_image(conn: sqlite3.Connection, *, product_id: int, local_path: str) -> None:
    """Registra uma imagem baixada do Telegram para o produto. A primeira
    imagem vence: só vira a foto principal (products.image_url) se o
    produto ainda não tiver nenhuma — nunca sobrescreve uma já conhecida,
    mesmo princípio "nunca apagar dado bom" já usado em
    update_product_price_stats para o parcelamento. O prefixo /media/ aqui
    precisa ficar em sincronia com o StaticFiles mount em app/api/main.py."""
    filename = os.path.basename(local_path)
    image_url = f"/media/{filename}"
    became_primary = update_product_image_url_if_null(conn, product_id, image_url)
    insert_product_image(
        conn, product_id=product_id, local_path=local_path, image_url=image_url,
        source="TELEGRAM_MEDIA", is_primary=became_primary,
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
    """Mescla todos os dados dependentes em uma única transação SQLite."""
    if source_product_id == target_product_id:
        raise ValueError("Não é possível mesclar um produto com ele mesmo.")

    try:
        conn.execute("BEGIN IMMEDIATE")
        source = conn.execute(
            "SELECT * FROM products WHERE id = ?", (source_product_id,)
        ).fetchone()
        target = conn.execute(
            "SELECT * FROM products WHERE id = ?", (target_product_id,)
        ).fetchone()
        if source is None or target is None:
            raise ValueError("Produto de origem ou destino não encontrado.")
        if source["status"] == "MERGED":
            raise ValueError("O produto de origem já foi mesclado.")
        if target["status"] != "ACTIVE":
            raise ValueError("O produto de destino precisa estar ativo.")

        # Favoritos são idempotentes: se qualquer um era favorito, o destino é.
        conn.execute(
            """
            INSERT OR IGNORE INTO favorites (product_id)
            SELECT ? WHERE EXISTS (
                SELECT 1 FROM favorites WHERE product_id IN (?, ?)
            )
            """,
            (target_product_id, source_product_id, target_product_id),
        )
        conn.execute("DELETE FROM favorites WHERE product_id = ?", (source_product_id,))

        # Alertas conflitantes são combinados preservando a opção mais abrangente.
        source_alert = conn.execute(
            "SELECT * FROM product_alerts WHERE product_id = ?", (source_product_id,)
        ).fetchone()
        target_alert = conn.execute(
            "SELECT * FROM product_alerts WHERE product_id = ?", (target_product_id,)
        ).fetchone()
        if source_alert is not None and target_alert is None:
            conn.execute(
                """
                UPDATE product_alerts
                SET product_id = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (target_product_id, source_alert["id"]),
            )
        elif source_alert is not None and target_alert is not None:
            if source_alert["max_price"] is None or target_alert["max_price"] is None:
                merged_max_price = None
            else:
                merged_max_price = max(source_alert["max_price"], target_alert["max_price"])
            conn.execute(
                """
                UPDATE product_alerts
                SET enabled = ?, max_price = ?, send_to_telegram = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    int(bool(source_alert["enabled"]) or bool(target_alert["enabled"])),
                    merged_max_price,
                    int(
                        bool(source_alert["send_to_telegram"])
                        or bool(target_alert["send_to_telegram"])
                    ),
                    target_alert["id"],
                ),
            )
            conn.execute("DELETE FROM product_alerts WHERE id = ?", (source_alert["id"],))

        # Specs repetidas mantêm a versão já consolidada no destino.
        conn.execute(
            """
            INSERT OR IGNORE INTO product_specs
                (product_id, spec_key, spec_value, confidence, source)
            SELECT ?, spec_key, spec_value, confidence, source
            FROM product_specs
            WHERE product_id = ?
            """,
            (target_product_id, source_product_id),
        )
        conn.execute("DELETE FROM product_specs WHERE product_id = ?", (source_product_id,))

        conn.execute(
            "UPDATE product_images SET product_id = ? WHERE product_id = ?",
            (target_product_id, source_product_id),
        )
        conn.execute(
            """
            UPDATE products
            SET image_url = COALESCE(image_url, ?),
                first_seen_at = MIN(first_seen_at, ?),
                last_seen_at = MAX(last_seen_at, ?),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                source["image_url"],
                source["first_seen_at"],
                source["last_seen_at"],
                target_product_id,
            ),
        )

        conn.execute(
            "UPDATE promotions SET product_id = ? WHERE product_id = ?",
            (target_product_id, source_product_id),
        )
        conn.execute(
            "UPDATE product_price_history SET product_id = ? WHERE product_id = ?",
            (target_product_id, source_product_id),
        )

        lowest = conn.execute(
            """
            SELECT price, recorded_at
            FROM product_price_history
            WHERE product_id = ?
            ORDER BY price ASC, recorded_at ASC, id ASC
            LIMIT 1
            """,
            (target_product_id,),
        ).fetchone()
        latest = conn.execute(
            """
            SELECT price, recorded_at
            FROM product_price_history
            WHERE product_id = ?
            ORDER BY recorded_at DESC, id DESC
            LIMIT 1
            """,
            (target_product_id,),
        ).fetchone()
        if lowest is not None and latest is not None:
            conn.execute(
                """
                UPDATE products
                SET lowest_price_ever = ?, lowest_price_ever_at = ?,
                    last_price = ?, last_price_at = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    lowest["price"],
                    lowest["recorded_at"],
                    latest["price"],
                    latest["recorded_at"],
                    target_product_id,
                ),
            )

        installment = conn.execute(
            """
            SELECT installment_count, installment_price, installment_no_interest
            FROM promotions
            WHERE product_id = ? AND installment_count IS NOT NULL
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (target_product_id,),
        ).fetchone()
        if installment is not None:
            conn.execute(
                """
                UPDATE products
                SET last_installment_count = ?, last_installment_price = ?,
                    last_installment_no_interest = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    installment["installment_count"],
                    installment["installment_price"],
                    installment["installment_no_interest"],
                    target_product_id,
                ),
            )

        conn.execute(
            """
            UPDATE products
            SET status = 'MERGED', merged_into_product_id = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (target_product_id, source_product_id),
        )
        conn.execute(
            """
            INSERT INTO product_merges (source_product_id, target_product_id, reason)
            VALUES (?, ?, ?)
            """,
            (source_product_id, target_product_id, reason),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


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
