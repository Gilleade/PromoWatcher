import json
import sqlite3
from dataclasses import dataclass
from typing import List, Optional

from app.database import (
    insert_match_queue_item,
    insert_occurrence,
    insert_promotion,
    insert_raw_message,
    update_promotion_product_match,
)
from app.models import AlertDef
from app.parser.link_resolver import LinkResult, LinkStatus, resolve_links
from app.parser.text_parser import ParsedMessage, parse_message
from app.products.matcher import DECISION_NEEDS_REVIEW
from app.products.product_service import get_or_create_product
from app.products.spec_extractor import extract_specs
from app.rules.alert_matcher import MatchResult, match_alerts
from app.rules.deduplicator import compute_dedupe_key, find_existing_promotion_id
from app.rules.score import ScoreResult, compute_score

NO_MATCH_REASON = "Ignorado: nenhum alerta cadastrado casou com a mensagem."


def _apply_product_matching(conn: sqlite3.Connection, promotion_id: int, parsed: ParsedMessage) -> None:
    """Casa a promoção com um perfil de produto do catálogo. Só roda quando há
    preço (mensagens sem preço não viram produto). Não tem try/except próprio
    de propósito: extract_specs() já nunca lança exceção (retorna specs
    vazias na dúvida), e um erro aqui em diante seria um bug real de SQL —
    deixa propagar para o [handler] erro: ... do watch_promos.py, igual ao
    resto do pipeline de alertas."""
    if parsed.price is None:
        return

    specs = extract_specs(parsed.raw_text)
    product_id, decision = get_or_create_product(conn, specs)
    update_promotion_product_match(
        conn,
        promotion_id=promotion_id,
        product_id=product_id,
        match_status=decision.decision,
        confidence=decision.confidence,
    )
    if decision.decision == DECISION_NEEDS_REVIEW:
        specs_json = json.dumps({
            "brand": specs.brand,
            "model": specs.model,
            "storage_gb": specs.storage_gb,
            "ram_gb": specs.ram_gb,
            "release_year": specs.release_year,
            "category": specs.category,
        })
        candidates_json = json.dumps([
            {"product_id": c.product_id, "confidence": c.confidence, "reason": c.reason}
            for c in decision.candidates
        ])
        insert_match_queue_item(
            conn,
            promotion_id=promotion_id,
            extracted_specs_json=specs_json,
            candidate_products_json=candidates_json,
        )


@dataclass
class ProcessResult:
    status: str  # NEW_APPROVED | NEW_IGNORED | DUPLICATE
    raw_message_id: int
    promotion_id: Optional[int]
    reason: str
    score: Optional[int] = None
    matched_alert: Optional[AlertDef] = None
    notify: bool = False
    parsed: Optional[ParsedMessage] = None
    link_result: Optional[LinkResult] = None
    repeat_count: Optional[int] = None


def _pick_best_match(matches: List[MatchResult], parsed: ParsedMessage,
                      store_domain: Optional[str]) -> tuple:
    """Retorna (matched_result, score_result) do melhor alerta aprovado, ou
    (None, None) se nenhum alerta bateu com score suficiente."""
    approved = []
    for match_result in matches:
        if not match_result.matched:
            continue
        score_result = compute_score(
            normalized_text=parsed.normalized_text,
            price=parsed.price,
            match_result=match_result,
            store_domain=store_domain,
        )
        if score_result.score >= match_result.alert.min_score:
            approved.append((match_result, score_result))

    if not approved:
        return None, None
    approved.sort(key=lambda pair: pair[1].score, reverse=True)
    return approved[0]


def process(conn: sqlite3.Connection, *, telegram_message_id: int, chat_id: int,
            chat_title: Optional[str], sender_id: Optional[int], message_text: str,
            message_date: str, alerts: List[AlertDef], has_media: bool = False,
            media_type: Optional[str] = None, raw_json: Optional[str] = None,
            accent_insensitive: bool = True, normalize_spaces_dashes: bool = True,
            case_insensitive: bool = True, link_resolve_timeout: float = 5.0) -> ProcessResult:
    raw_message_id = insert_raw_message(
        conn,
        telegram_message_id=telegram_message_id,
        chat_id=chat_id,
        chat_title=chat_title,
        sender_id=sender_id,
        message_text=message_text,
        message_date=message_date,
        has_media=has_media,
        media_type=media_type,
        raw_json=raw_json,
    )

    parsed = parse_message(
        message_text,
        accent_insensitive=accent_insensitive,
        normalize_spaces_dashes=normalize_spaces_dashes,
        case_insensitive=case_insensitive,
    )

    link_result = resolve_links(parsed.links, timeout=link_resolve_timeout)

    dedupe_key = compute_dedupe_key(link_result, parsed.title_guess, parsed.price)

    existing_promotion_id = find_existing_promotion_id(conn, dedupe_key)
    if existing_promotion_id is not None:
        insert_occurrence(
            conn,
            promotion_id=existing_promotion_id,
            raw_message_id=raw_message_id,
            chat_title=chat_title,
            message_date=message_date,
            original_url=parsed.links[0] if parsed.links else None,
        )
        return ProcessResult(
            status="DUPLICATE",
            raw_message_id=raw_message_id,
            promotion_id=existing_promotion_id,
            reason="Duplicado porque já existe promoção com a mesma chave de deduplicação.",
            parsed=parsed,
            link_result=link_result,
        )

    matches = match_alerts(parsed.normalized_text, alerts)
    best_match, best_score = _pick_best_match(matches, parsed, link_result.store_domain)

    if best_match is None:
        blocked = next((m for m in matches if m.matched_excluded), None)
        reason = blocked.reason if blocked else NO_MATCH_REASON
        promotion_id = insert_promotion(
            conn,
            raw_message_id=raw_message_id,
            title_guess=parsed.title_guess,
            price=float(parsed.price) if parsed.price is not None else None,
            old_price=float(parsed.old_price) if parsed.old_price is not None else None,
            discount_percent=float(parsed.discount_percent) if parsed.discount_percent is not None else None,
            coupon=parsed.coupon,
            source_chat_title=chat_title,
            original_links=",".join(parsed.links) if parsed.links else None,
            selected_original_url=parsed.links[0] if parsed.links else None,
            resolved_url=link_result.url if link_result.status in
            (LinkStatus.RESOLVED, LinkStatus.MULTIPLE_LINKS) else None,
            clean_url=link_result.url if link_result.status == LinkStatus.CLEANED else None,
            link_status=link_result.status.value,
            store_domain=link_result.store_domain,
            dedupe_key=dedupe_key,
            status="IGNORED",
            score=None,
        )
        _apply_product_matching(conn, promotion_id, parsed)
        return ProcessResult(
            status="NEW_IGNORED",
            raw_message_id=raw_message_id,
            promotion_id=promotion_id,
            reason=reason,
            parsed=parsed,
            link_result=link_result,
        )

    promotion_id = insert_promotion(
        conn,
        raw_message_id=raw_message_id,
        title_guess=parsed.title_guess,
        price=float(parsed.price) if parsed.price is not None else None,
        old_price=float(parsed.old_price) if parsed.old_price is not None else None,
        discount_percent=float(parsed.discount_percent) if parsed.discount_percent is not None else None,
        coupon=parsed.coupon,
        source_chat_title=chat_title,
        original_links=",".join(parsed.links) if parsed.links else None,
        selected_original_url=parsed.links[0] if parsed.links else None,
        resolved_url=link_result.url if link_result.status in
        (LinkStatus.RESOLVED, LinkStatus.MULTIPLE_LINKS) else None,
        clean_url=link_result.url if link_result.status == LinkStatus.CLEANED else None,
        link_status=link_result.status.value,
        store_domain=link_result.store_domain,
        dedupe_key=dedupe_key,
        status="APPROVED",
        score=best_score.score,
        matched_alert_id=best_match.alert.id,
    )
    _apply_product_matching(conn, promotion_id, parsed)

    return ProcessResult(
        status="NEW_APPROVED",
        raw_message_id=raw_message_id,
        promotion_id=promotion_id,
        reason=f"{best_match.reason} {best_score.reason}",
        score=best_score.score,
        matched_alert=best_match.alert,
        notify=best_match.alert.send_to_telegram,
        parsed=parsed,
        link_result=link_result,
    )
