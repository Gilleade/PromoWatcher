import sqlite3
from dataclasses import dataclass
from typing import Optional

from app.database import find_coupon_by_dedupe_key, insert_coupon, touch_coupon_seen
from app.parser.coupon_signal import extract_discount_label
from app.parser.link_resolver import LinkResult
from app.parser.text_parser import ParsedMessage


@dataclass
class CouponResult:
    status: str  # NEW_COUPON | DUPLICATE_COUPON
    coupon_id: int


def compute_coupon_dedupe_key(*, code: Optional[str], store_domain: Optional[str],
                               url: Optional[str], discount_label: Optional[str]) -> str:
    """Hierarquia própria (não reaproveita a de produtos): código+loja é o
    identificador mais forte de um cupom; na ausência, cai pra URL, depois
    pro selo de desconto+loja, e por fim só o selo (evita que dois cupons
    de lojas diferentes com o mesmo texto "R$20 OFF" colidam)."""
    if code and store_domain:
        return f"code:{store_domain}:{code.strip().upper()}"
    if code:
        return f"code:{code.strip().upper()}"
    if url:
        return f"url:{url}"
    if discount_label and store_domain:
        return f"label:{store_domain}:{discount_label.strip().upper()}"
    return f"label:{(discount_label or 'generic').strip().upper()}"


def process_coupon_message(conn: sqlite3.Connection, *, raw_message_id: int, parsed: ParsedMessage,
                            link_result: LinkResult, chat_title: Optional[str]) -> CouponResult:
    discount_label = extract_discount_label(parsed.raw_text)
    url = parsed.links[0] if parsed.links else None
    dedupe_key = compute_coupon_dedupe_key(
        code=parsed.coupon, store_domain=link_result.store_domain, url=url,
        discount_label=discount_label,
    )

    existing = find_coupon_by_dedupe_key(conn, dedupe_key)
    if existing:
        touch_coupon_seen(conn, existing["id"])
        return CouponResult(status="DUPLICATE_COUPON", coupon_id=existing["id"])

    coupon_id = insert_coupon(
        conn,
        raw_message_id=raw_message_id,
        dedupe_key=dedupe_key,
        code=parsed.coupon,
        discount_label=discount_label,
        description=parsed.title_guess,
        store_domain=link_result.store_domain,
        url=url,
        source_chat_title=chat_title,
    )
    return CouponResult(status="NEW_COUPON", coupon_id=coupon_id)
