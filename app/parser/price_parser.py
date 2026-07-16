import re
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple

_PRICE_RS = re.compile(
    r"R\$\s*("
    r"\d{1,3}(?:\.\d{3})+,\d{2}"
    r"|\d+,\d{2}"
    r"|\d{1,3}(?:\.\d{3})+"
    r"|\d+"
    r")"
)
_PRICE_REAIS = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*reais", re.IGNORECASE)

_COUPON_RE = re.compile(r"(?i:cupom)\s*[:\-]?\s*([A-Z0-9]{3,20})")

# "R$20 OFF" é um valor de desconto de cupom, não o preço de um produto —
# um match de preço imediatamente seguido de "OFF" não conta como preço.
# Sem "^": pattern.match(text, pos) já ancora em pos; "^" checaria o início
# absoluto da string (posição 0), não pos, e nunca bateria aqui.
_OFF_SUFFIX_RE = re.compile(r"\s*off\b", re.IGNORECASE)

# "Em até 8x de R$ 52,50 sem juros" é o valor da PARCELA do parcelamento,
# não o preço à vista — um preço imediatamente precedido por um contador
# de parcelas ("8x", "8x de") não conta como preço do produto. Sem essa
# exclusão, "8x de R$52,50" vira o último preço do texto e sobrescreve o
# preço "por R$ ..." real (bug real observado em produção: uma promoção
# de monitor com "DE R$499 / POR R$420 / 8x de R$52,50" gravou R$52,50
# como preço final).
_INSTALLMENT_PREFIX_RE = re.compile(r"\d+\s*x\s*(?:de\s*)?$", re.IGNORECASE)


def _to_decimal(raw: str) -> Optional[Decimal]:
    normalized = raw.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def extract_prices(text: str) -> List[Decimal]:
    if not text:
        return []
    matches = []
    for m in _PRICE_RS.finditer(text):
        if _OFF_SUFFIX_RE.match(text, m.end()):
            continue
        if _INSTALLMENT_PREFIX_RE.search(text, 0, m.start()):
            continue
        matches.append((m.start(), m.group(1)))
    for m in _PRICE_REAIS.finditer(text):
        if _INSTALLMENT_PREFIX_RE.search(text, 0, m.start()):
            continue
        matches.append((m.start(), m.group(1)))
    matches.sort(key=lambda x: x[0])

    prices = []
    for _, raw in matches:
        value = _to_decimal(raw)
        if value is not None:
            prices.append(value)
    return prices


def extract_price(text: str) -> Optional[Decimal]:
    prices = extract_prices(text)
    return prices[-1] if prices else None


def extract_price_range(text: str) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """Retorna (old_price, price). Se houver 2+ preços, assume o primeiro como
    preço antigo e o último como preço final (padrão "de X por Y")."""
    prices = extract_prices(text)
    if not prices:
        return None, None
    if len(prices) == 1:
        return None, prices[0]
    return prices[0], prices[-1]


def extract_coupon(text: str) -> Optional[str]:
    if not text:
        return None
    m = _COUPON_RE.search(text)
    return m.group(1) if m else None
