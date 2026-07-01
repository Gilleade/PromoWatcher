import sqlite3
from decimal import Decimal
from typing import Optional
from urllib.parse import urlsplit

from app.database import find_promotion_by_dedupe_key
from app.parser.link_resolver import LinkResult, LinkStatus
from app.parser.normalizer import normalize_text


def _domain_path_key(url: str) -> Optional[str]:
    try:
        parts = urlsplit(url)
        if not parts.netloc:
            return None
        return f"{parts.netloc.lower()}{parts.path.rstrip('/').lower()}"
    except Exception:
        return None


def compute_dedupe_key(link_result: LinkResult, title: Optional[str],
                        price: Optional[Decimal]) -> str:
    """Segue a hierarquia: clean_url > resolved_url > domínio+path > título+preço."""
    if link_result.status == LinkStatus.CLEANED and link_result.url:
        return f"clean:{link_result.url}"

    if link_result.status == LinkStatus.RESOLVED and link_result.url:
        return f"resolved:{link_result.url}"

    if link_result.url:
        domain_path = _domain_path_key(link_result.url)
        if domain_path:
            return f"domain:{domain_path}"

    if title:
        normalized_title = normalize_text(title)
        price_part = str(price) if price is not None else "no-price"
        return f"title:{normalized_title}:{price_part}"

    price_part = str(price) if price is not None else "no-price"
    return f"notitle:{price_part}"


def find_existing_promotion_id(conn: sqlite3.Connection, dedupe_key: str) -> Optional[int]:
    row = find_promotion_by_dedupe_key(conn, dedupe_key)
    return row["id"] if row else None
