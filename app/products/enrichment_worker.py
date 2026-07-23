import asyncio
import json
import sqlite3
from typing import Callable, Optional

from app.config import Config
from app.database import (
    fetch_products_by_ids,
    find_product_by_variant_key,
    get_next_pending_match_queue_item,
    get_promotion_with_raw_text,
    insert_product,
    touch_product_seen,
    update_match_queue_status,
    update_promotion_product_match,
)
from app.products.hybrid_classifier import classify_hybrid
from app.products.matcher import find_candidates
from app.products.ollama_client import (
    OllamaExtractionResult,
    OllamaMatchResult,
    disambiguate_product,
    extract_specs_via_ollama,
)
from app.products.product_service import record_price_point
from app.products.spec_extractor import ExtractedSpecs, build_variant_key

# Quantas vezes um item pode voltar pra fila como PENDING antes de ser
# encerrado como NEEDS_HUMAN (dá resiliência a indisponibilidade passageira
# do Ollama sem deixar item preso pra sempre esperando).
MAX_ATTEMPTS = 3
MIN_AI_MATCH_CONFIDENCE = 0.80
MIN_AI_NEW_CONFIDENCE = 0.90


def _merge_missing_specs(specs: dict, extraction: OllamaExtractionResult) -> dict:
    """A IA só preenche lacunas; nunca sobrescreve um dado determinístico."""
    merged = dict(specs)
    if not extraction.ok:
        return merged
    for field in ("brand", "model", "storage_gb", "ram_gb", "category", "release_year"):
        if merged.get(field) is None and getattr(extraction, field) is not None:
            merged[field] = getattr(extraction, field)
    found_fields = sum(merged.get(field) is not None for field in ("brand", "model", "storage_gb"))
    merged["completeness_confidence"] = found_fields / 3.0
    return merged


def _as_extracted_specs(specs: dict) -> ExtractedSpecs:
    return ExtractedSpecs(
        brand=specs.get("brand"),
        model=specs.get("model"),
        storage_gb=specs.get("storage_gb"),
        ram_gb=specs.get("ram_gb"),
        release_year=specs.get("release_year"),
        category=specs.get("category"),
        completeness_confidence=float(specs.get("completeness_confidence") or 0.0),
    )


def _new_identity(specs: dict, result: OllamaMatchResult) -> tuple:
    brand = result.brand or specs.get("brand")
    model = result.model or specs.get("model")
    storage_gb = result.storage_gb if result.storage_gb is not None else specs.get("storage_gb")
    ram_gb = result.ram_gb if result.ram_gb is not None else specs.get("ram_gb")
    return brand, model, storage_gb, ram_gb


def _candidate_dicts(candidate_rows: list) -> list:
    return [
        {
            "id": row["id"],
            "canonical_title": row["canonical_title"],
            "brand": row["brand"],
            "model": row["model"],
            "storage_gb": row["storage_gb"],
            "ram_gb": row["ram_gb"],
        }
        for row in candidate_rows
    ]


def _finalize_match(conn: sqlite3.Connection, *, promotion_row: sqlite3.Row, product_id: int,
                     match_status: str, confidence: float) -> None:
    touch_product_seen(conn, product_id)
    update_promotion_product_match(
        conn, promotion_id=promotion_row["id"], product_id=product_id,
        match_status=match_status, confidence=confidence,
    )
    if promotion_row["price"] is not None:
        record_price_point(
            conn,
            product_id=product_id,
            promotion_id=promotion_row["id"],
            price=promotion_row["price"],
            old_price=promotion_row["old_price"],
            coupon=promotion_row["coupon"],
            store_domain=promotion_row["store_domain"],
            source_chat_title=promotion_row["source_chat_title"],
        )


def _create_product_from_ollama(conn: sqlite3.Connection, specs: dict, result: OllamaMatchResult) -> int:
    """Cria um produto novo a partir da decisão NEW da IA — usa os campos que
    o modelo retornou (pode ter refinado marca/modelo comparando com os
    candidatos), com fallback pras specs determinísticas originais."""
    brand = result.brand or specs.get("brand")
    model = result.model or specs.get("model")
    storage_gb = result.storage_gb if result.storage_gb is not None else specs.get("storage_gb")
    ram_gb = result.ram_gb if result.ram_gb is not None else specs.get("ram_gb")
    canonical_title = result.canonical_title or " ".join(
        filter(None, [brand.title() if brand else None, model.title() if model else None])
    ) or "Produto não identificado"

    return insert_product(
        conn,
        canonical_title=canonical_title,
        variant_key=build_variant_key(brand, model, storage_gb, ram_gb),
        category=specs.get("category"),
        brand=brand,
        model=model,
        storage_gb=storage_gb,
        ram_gb=ram_gb,
        release_year=specs.get("release_year"),
    )


def process_match_queue_once(conn: sqlite3.Connection, config: Config) -> bool:
    """Processa um item pendente sem aceitar decisões ambíguas da IA."""
    item = get_next_pending_match_queue_item(conn)
    if item is None:
        return False

    attempts = item["attempts"] + 1
    specs = json.loads(item["extracted_specs_json"])
    if specs.get("review_reason") == "MULTIPLE_PRODUCTS":
        result_json = json.dumps({"decision": "NEEDS_HUMAN", "reason": "MULTIPLE_PRODUCTS"})
        update_promotion_product_match(
            conn, promotion_id=item["promotion_id"], product_id=None,
            match_status="NEEDS_HUMAN", confidence=0.0,
        )
        update_match_queue_status(
            conn, item["id"], status="NEEDS_HUMAN", attempts=attempts, result_json=result_json,
        )
        return True

    promotion = get_promotion_with_raw_text(conn, item["promotion_id"])
    if promotion is None:
        result_json = json.dumps({"decision": "NEEDS_HUMAN", "reason": "PROMOTION_NOT_FOUND"})
        update_match_queue_status(
            conn, item["id"], status="NEEDS_HUMAN", attempts=attempts, result_json=result_json,
        )
        return True
    raw_text = promotion["raw_message_text"]

    original_specs = dict(specs)
    extraction = None
    hybrid = None
    if config.ollama_enabled and (
        config.ollama_shadow_mode or not specs.get("brand") or not specs.get("model")
    ):
        extraction = extract_specs_via_ollama(config, raw_text)
        if config.ollama_shadow_mode:
            hybrid = classify_hybrid(
                deterministic_specs=original_specs,
                ai_extraction=extraction,
                raw_text=raw_text,
            )
            specs = dict(original_specs)
            specs.update(hybrid.validated_ai_fields)
            found_fields = sum(
                specs.get(field) is not None for field in ("brand", "model", "storage_gb")
            )
            specs["completeness_confidence"] = found_fields / 3.0
        else:
            specs = _merge_missing_specs(specs, extraction)

    raw_candidates = json.loads(item["candidate_products_json"] or "[]")
    candidate_ids = {
        candidate["product_id"]
        for candidate in raw_candidates
        if candidate.get("product_id") is not None
    }
    if extraction is not None and extraction.ok:
        candidate_ids.update(
            candidate.product_id for candidate in find_candidates(conn, _as_extracted_specs(specs))
        )
    candidate_rows = fetch_products_by_ids(conn, list(candidate_ids))
    candidates = _candidate_dicts(candidate_rows)

    result = disambiguate_product(config, extracted=specs, raw_text=raw_text, candidates=candidates)
    result_payload = {
        "decision": result.decision,
        "product_id": result.product_id,
        "confidence": result.confidence,
        "reason": result.reason,
        "enriched_specs": specs,
    }

    if config.ollama_shadow_mode:
        hybrid = hybrid or classify_hybrid(
            deterministic_specs=original_specs,
            ai_extraction=extraction,
            raw_text=raw_text,
        )
        result_payload["hybrid_classification"] = hybrid.as_dict()

    result_json = json.dumps(result_payload)

    if config.ollama_shadow_mode:
        update_match_queue_status(
            conn,
            item["id"],
            status="SHADOW_DONE",
            attempts=attempts,
            result_json=result_json,
        )
        return True

    valid_candidate_ids = {candidate["id"] for candidate in candidates}
    if (
        result.decision == "MATCH"
        and result.product_id in valid_candidate_ids
        and result.confidence >= MIN_AI_MATCH_CONFIDENCE
    ):
        _finalize_match(
            conn, promotion_row=promotion, product_id=result.product_id,
            match_status="AUTO_MATCH_AI", confidence=result.confidence,
        )
        update_match_queue_status(
            conn, item["id"], status="DONE", attempts=attempts, result_json=result_json,
        )
        return True

    brand, model, storage_gb, ram_gb = _new_identity(specs, result)
    can_create = (
        result.decision == "NEW"
        and result.confidence >= MIN_AI_NEW_CONFIDENCE
        and isinstance(brand, str) and bool(brand.strip())
        and isinstance(model, str) and bool(model.strip())
    )
    if can_create:
        variant_key = build_variant_key(brand, model, storage_gb, ram_gb)
        existing = find_product_by_variant_key(conn, variant_key)
        if existing is not None:
            product_id = existing["id"]
            match_status = "AUTO_MATCH_AI"
        else:
            product_id = _create_product_from_ollama(conn, specs, result)
            match_status = "AUTO_NEW_AI"
        _finalize_match(
            conn, promotion_row=promotion, product_id=product_id,
            match_status=match_status, confidence=result.confidence,
        )
        update_match_queue_status(
            conn, item["id"], status="DONE", attempts=attempts, result_json=result_json,
        )
        return True

    # UNSURE, baixa confiança ou id fora da lista: revisão humana.
    if attempts >= MAX_ATTEMPTS:
        update_promotion_product_match(
            conn, promotion_id=item["promotion_id"], product_id=None,
            match_status="NEEDS_HUMAN", confidence=result.confidence,
        )
        update_match_queue_status(
            conn, item["id"], status="NEEDS_HUMAN", attempts=attempts, result_json=result_json,
        )
    else:
        update_match_queue_status(
            conn, item["id"], status="PENDING", attempts=attempts, result_json=result_json,
        )
    return True


def _process_one_in_thread(get_conn: Callable[[], sqlite3.Connection], config: Config) -> bool:
    """A conexão SQLite precisa ser criada na MESMA thread onde é usada (o
    sqlite3 do stdlib amarra a conexão à thread que a abriu) — por isso
    get_conn() roda aqui dentro, na worker thread do executor, e não no loop
    principal do asyncio."""
    conn = get_conn()
    try:
        return process_match_queue_once(conn, config)
    finally:
        conn.close()


async def run_enrichment_cycle(get_conn: Callable[[], sqlite3.Connection], config: Config,
                                loop: Optional[asyncio.AbstractEventLoop] = None) -> int:
    """Drena a fila de casamento pendente, um item por vez — sem paralelismo
    (a GPU de 4GB não aguenta concorrência). Cada chamada roda em thread
    separada via run_in_executor para não travar o loop do Telethon.
    Retorna quantos itens foram processados neste ciclo."""
    loop = loop or asyncio.get_event_loop()
    processed_count = 0
    while True:
        processed = await loop.run_in_executor(None, _process_one_in_thread, get_conn, config)
        if not processed:
            break
        processed_count += 1
    return processed_count


async def enrichment_worker_loop(get_conn: Callable[[], sqlite3.Connection], config: Config,
                                  poll_interval_seconds: float = 25.0) -> None:
    """Task de fundo pensada para rodar no mesmo event loop do Telethon
    (client.loop.create_task(...)). Nunca propaga exceção — um erro aqui não
    pode derrubar o watcher."""
    while True:
        await asyncio.sleep(poll_interval_seconds)
        try:
            processed = await run_enrichment_cycle(get_conn, config)
            if processed:
                print(f"[enrichment] {processed} item(ns) da fila de produtos processado(s).")
        except Exception as e:
            print(f"[enrichment] erro: {type(e).__name__}: {e}")
