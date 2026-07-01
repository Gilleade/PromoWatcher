from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from app.parser.link_extractor import extract_links
from app.parser.normalizer import normalize_text
from app.parser.price_parser import extract_coupon, extract_price_range


@dataclass
class ParsedMessage:
    raw_text: str
    normalized_text: str
    title_guess: Optional[str]
    price: Optional[Decimal]
    old_price: Optional[Decimal]
    discount_percent: Optional[Decimal]
    coupon: Optional[str]
    links: List[str]


def guess_title(text: str) -> Optional[str]:
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        if candidate.startswith("http") or candidate.startswith("R$"):
            continue
        return candidate
    return None


def compute_discount_percent(old_price: Optional[Decimal], price: Optional[Decimal]) -> Optional[Decimal]:
    if not old_price or not price or old_price <= 0:
        return None
    return ((old_price - price) / old_price * 100).quantize(Decimal("0.1"))


def parse_message(text: str, *, accent_insensitive: bool = True,
                   normalize_spaces_dashes: bool = True, case_insensitive: bool = True) -> ParsedMessage:
    text = text or ""
    old_price, price = extract_price_range(text)
    return ParsedMessage(
        raw_text=text,
        normalized_text=normalize_text(
            text,
            accent_insensitive=accent_insensitive,
            normalize_spaces_dashes=normalize_spaces_dashes,
            case_insensitive=case_insensitive,
        ),
        title_guess=guess_title(text),
        price=price,
        old_price=old_price,
        discount_percent=compute_discount_percent(old_price, price),
        coupon=extract_coupon(text),
        links=extract_links(text),
    )
