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

_COUPON_RE = re.compile(
    r"(?i:\b(?:use\s+o\s+)?cupom\b|\bcodigo\b)\s*[:\-]?\s*"
    r"(?:(?i:de|do|da)\s+)?([A-Z0-9][A-Z0-9_-]{2,29})"
)
_COUPON_COLON_RE = re.compile(r"[:\-]\s*([A-Z0-9][A-Z0-9_-]{2,29})\b")
_COUPON_STOPWORDS = {
    "APP", "AMAZON", "AQUI", "CODIGO", "DESCONTO", "LOJA", "MERCADO",
    "LIVRE", "OFF", "SITE", "SHOPEE",
}
_COUPON_SIGNAL_RE = re.compile(r"\bcupom\b|\d{1,3}%\s*off|r\$\s*\d+[.,]?\d*\s*off", re.IGNORECASE)
_COUPON_ANNOUNCEMENT_RE = re.compile(
    r"^[^\w]*(?:(?:alerta\s+de|nov[oa])\s+)?(?:cupom|cupons)\b", re.IGNORECASE
)

# "R$20 OFF" é um valor de desconto de cupom, não o preço de um produto —
# um match de preço imediatamente seguido de "OFF" não conta como preço.
# Sem "^": pattern.match(text, pos) já ancora em pos; "^" checaria o início
# absoluto da string (posição 0), não pos, e nunca bateria aqui.
_OFF_SUFFIX_RE = re.compile(r"\s*off\b", re.IGNORECASE)
_COUPON_AMOUNT_SUFFIX_RE = re.compile(
    r"\s*(?:off\b|de desconto\b|acima de\b|em compras\b|em\s+r\$)",
    re.IGNORECASE,
)
_THRESHOLD_PREFIX_RE = re.compile(
    r"(?:acima de|a partir de|compras? (?:acima de|a partir de)|limite(?: de)?|"
    r"minimo(?: de)?|mínimo(?: de)?)\s*$",
    re.IGNORECASE,
)
_COUPON_EM_PREFIX_RE = re.compile(r"\bem\s*$", re.IGNORECASE)
_OLD_PRICE_PREFIX_RE = re.compile(r"\b(?:de|era|antes)\s*:?\s*$", re.IGNORECASE)
_FINAL_PRICE_PREFIX_RE = re.compile(r"\b(?:por|so|só|apenas|somente)\s*:?\s*$", re.IGNORECASE)
_PIX_CONTEXT_RE = re.compile(r"^(?:\s*(?:no|via)?\s*pix\b|\s*a vista\b|\s*à vista\b|\s*na recorrencia\b)", re.IGNORECASE)
_CARD_CONTEXT_RE = re.compile(r"^\s*(?:no cartao|no cartão|em ate|em até|parcelado)", re.IGNORECASE)

# "Em até 8x de R$ 52,50 sem juros" é o valor da PARCELA do parcelamento,
# não o preço à vista — um preço imediatamente precedido por um contador
# de parcelas ("8x", "8x de") não conta como preço do produto. Sem essa
# exclusão, "8x de R$52,50" vira o último preço do texto e sobrescreve o
# preço "por R$ ..." real (bug real observado em produção: uma promoção
# de monitor com "DE R$499 / POR R$420 / 8x de R$52,50" gravou R$52,50
# como preço final).
_INSTALLMENT_PREFIX_RE = re.compile(r"\d+\s*x\s*(?:de\s*)?$", re.IGNORECASE)

# Captura o parcelamento em si (contador de parcelas + valor da parcela),
# para exibir ao lado do preço à vista — o inverso de _INSTALLMENT_PREFIX_RE,
# que só serve para EXCLUIR esse valor da extração de preço à vista.
_INSTALLMENT_RE = re.compile(
    r"(\d{1,2})\s*x\s*(?:de\s*)?R\$\s*("
    r"\d{1,3}(?:\.\d{3})+,\d{2}"
    r"|\d+,\d{2}"
    r"|\d{1,3}(?:\.\d{3})+"
    r"|\d+"
    r")",
    re.IGNORECASE,
)
_NO_INTEREST_RE = re.compile(r"sem\s+juros", re.IGNORECASE)


def _to_decimal(raw: str) -> Optional[Decimal]:
    normalized = raw.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _is_non_product_amount(text: str, match: re.Match) -> bool:
    before = text[max(0, match.start() - 45):match.start()]
    after = text[match.end():match.end() + 35]
    if _OFF_SUFFIX_RE.match(after):
        return True
    if _INSTALLMENT_PREFIX_RE.search(text, 0, match.start()):
        return True
    if _THRESHOLD_PREFIX_RE.search(before) or _COUPON_AMOUNT_SUFFIX_RE.match(after):
        return True
    if _COUPON_SIGNAL_RE.search(text) and _COUPON_EM_PREFIX_RE.search(before):
        return True
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    if (
        _COUPON_ANNOUNCEMENT_RE.search(first_line)
        and not _FINAL_PRICE_PREFIX_RE.search(before)
        and not _PIX_CONTEXT_RE.search(after)
    ):
        return True
    return False


def _extract_price_matches(text: str) -> List[Tuple[int, int, Decimal]]:
    if not text:
        return []

    raw_matches = []
    for match in _PRICE_RS.finditer(text):
        if not _is_non_product_amount(text, match):
            raw_matches.append((match.start(), match.end(), match.group(1)))
    for match in _PRICE_REAIS.finditer(text):
        if not _is_non_product_amount(text, match):
            raw_matches.append((match.start(), match.end(), match.group(1)))
    raw_matches.sort(key=lambda item: item[0])

    matches = []
    for start, end, raw in raw_matches:
        value = _to_decimal(raw)
        if value is not None:
            matches.append((start, end, value))
    return matches


def extract_prices(text: str) -> List[Decimal]:
    return [value for _, _, value in _extract_price_matches(text)]


def _final_price_score(text: str, start: int, end: int) -> int:
    before = text[max(0, start - 25):start]
    after = text[end:end + 35]
    if _PIX_CONTEXT_RE.search(after) or re.search(
        r"\b(?:pix|a vista|à vista|recorrencia)\s*:?\s*$", before, re.IGNORECASE
    ):
        return 50
    if _FINAL_PRICE_PREFIX_RE.search(before):
        return 35
    if _CARD_CONTEXT_RE.search(after):
        return 5
    return 10


def extract_price(text: str) -> Optional[Decimal]:
    _, price = extract_price_range(text)
    return price


def extract_price_range(text: str) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """Retorna preço anterior somente quando o texto o marca como tal.

    Entre opções de pagamento, PIX/à vista/recorrência têm prioridade sobre
    cartão. Isso evita transformar o valor mais alto parcelado em preço atual.
    """
    matches = _extract_price_matches(text)
    if not matches:
        return None, None

    selected = max(matches, key=lambda item: (_final_price_score(text, item[0], item[1]), item[0]))
    old_candidates = [
        item for item in matches
        if item != selected and _OLD_PRICE_PREFIX_RE.search(text[max(0, item[0] - 20):item[0]])
    ]
    old_price = old_candidates[0][2] if old_candidates else None
    return old_price, selected[2]


def _valid_coupon_code(code: str) -> bool:
    return code.upper() not in _COUPON_STOPWORDS


def extract_coupon(text: str) -> Optional[str]:
    if not text:
        return None
    for match in _COUPON_RE.finditer(text):
        code = match.group(1).upper()
        if _valid_coupon_code(code):
            return code
    if _COUPON_SIGNAL_RE.search(text):
        for match in _COUPON_COLON_RE.finditer(text):
            code = match.group(1).upper()
            if _valid_coupon_code(code):
                return code
    return None


def extract_installment(text: str) -> Optional[Tuple[int, Decimal, Optional[bool]]]:
    """Extrai o parcelamento ("Nx de R$Y") do texto, se houver — o primeiro
    trecho encontrado. Retorna (quantidade, valor_da_parcela, sem_juros).
    `sem_juros` é True quando "sem juros" aparece logo após o valor, e None
    quando a mensagem não menciona (ausência não significa que tem juros,
    só que a mensagem não disse)."""
    if not text:
        return None
    m = _INSTALLMENT_RE.search(text)
    if not m:
        return None
    unit_price = _to_decimal(m.group(2))
    if unit_price is None:
        return None
    no_interest = True if _NO_INTEREST_RE.search(text, m.end(), m.end() + 30) else None
    return int(m.group(1)), unit_price, no_interest
