from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from app.parser.link_extractor import extract_links
from app.parser.normalizer import normalize_text
from app.parser.price_parser import extract_coupon, extract_installment, extract_price_range
from app.parser.product_text import has_multiple_product_offers, select_product_line


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
    installment_count: Optional[int] = None
    installment_price: Optional[Decimal] = None
    installment_no_interest: Optional[bool] = None
    has_multiple_products: bool = False


def guess_title(text: str) -> Optional[str]:
    return select_product_line(text)


def compute_discount_percent(old_price: Optional[Decimal], price: Optional[Decimal]) -> Optional[Decimal]:
    if not old_price or not price or old_price <= 0:
        return None
    return ((old_price - price) / old_price * 100).quantize(Decimal("0.1"))


def parse_message(text: str, *, accent_insensitive: bool = True,
                   normalize_spaces_dashes: bool = True, case_insensitive: bool = True) -> ParsedMessage:
    text = text or ""
    has_multiple_products = has_multiple_product_offers(text)
    old_price, price = extract_price_range(text)
    if has_multiple_products:
        old_price, price = None, None
    installment = extract_installment(text)
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
        installment_count=installment[0] if installment else None,
        installment_price=installment[1] if installment else None,
        installment_no_interest=installment[2] if installment else None,
        has_multiple_products=has_multiple_products,
    )
