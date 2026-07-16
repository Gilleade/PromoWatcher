import re
from typing import Optional

from app.parser.text_parser import ParsedMessage

_DISCOUNT_LABEL_RE = re.compile(r"(r\$\s?\d+[.,]?\d*\s*off|\d{1,3}%\s*off)", re.IGNORECASE)

PRODUCT = "PRODUCT"
COUPON = "COUPON"


def extract_discount_label(text: str) -> Optional[str]:
    if not text:
        return None
    match = _DISCOUNT_LABEL_RE.search(text)
    return match.group(0).strip().upper() if match else None


def classify_message_kind(parsed: ParsedMessage) -> str:
    """PRODUCT (padrão) ou COUPON — mensagem com sinal de cupom/desconto
    (código de cupom ou selo tipo "R$20 OFF"/"30% OFF") mas sem preço de
    produto identificado, no estilo dos cupons "soltos" do Pelando (cupom
    publicado sem item específico associado)."""
    if parsed.price is not None:
        return PRODUCT
    if parsed.coupon or extract_discount_label(parsed.raw_text):
        return COUPON
    return PRODUCT
