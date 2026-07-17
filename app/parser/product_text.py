import re
from typing import Optional

from app.parser.normalizer import normalize_text


_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_MODEL_CODE_RE = re.compile(r"\b(?:[a-z]{1,8}[- ]?\d{2,}[a-z0-9-]*|\d{2,}[a-z]{1,8})\b", re.IGNORECASE)
_PRODUCT_TERMS_RE = re.compile(
    r"\b(?:smartphone|celular|iphone|ipad|tablet|notebook|laptop|macbook|monitor|"
    r"televisao|smart tv|fone|headset|earbud|soundbar|caixa de som|partybox|"
    r"teclado|mouse|controle|console|playstation|xbox|placa mae|placa de video|"
    r"processador|impressora|airtag|rastreador|relogio|smartwatch|tenis|esteira|"
    r"perfume|shampoo|fonte|ssd|gpu|fans?)\b"
)
_NON_TITLE_RE = re.compile(
    r"\b(?:cupom|compre aqui|link(?: do produto)?|resgate|frete gratis|site confiavel|"
    r"preco e estoque|anuncio|entre no grupo|encaminhe|compare os fretes|opcao\s*\d*)\b"
)
_PAYMENT_LINE_RE = re.compile(
    r"^(?:de|por|s[oó]|apenas|somente|ou|no pix|pix|no cart[aã]o|em at[eé]|r\$)\b",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(r"r\$\s*\d", re.IGNORECASE)
_COUPON_TITLE_RE = re.compile(r"\b(?:cupom|cupons)\b", re.IGNORECASE)


def _strip_leading_symbols(line: str) -> str:
    return re.sub(r"^[^\wR$]+", "", line).strip()


def _candidate_score(line: str, index: int) -> float:
    normalized = normalize_text(line)
    if not normalized or _URL_RE.search(line):
        return float("-inf")
    if _PAYMENT_LINE_RE.search(_strip_leading_symbols(line)):
        return float("-inf")

    words = re.findall(r"[a-z0-9]+", normalized)
    score = min(len(words), 10) * 0.35
    score += 5.0 if _PRODUCT_TERMS_RE.search(normalized) else 0.0
    score += 2.0 if _MODEL_CODE_RE.search(normalized) else 0.0
    score -= 5.0 if _NON_TITLE_RE.search(normalized) else 0.0
    score -= 4.0 if line.count("!") + line.count("?") >= 2 else 0.0
    score -= 2.0 if _PRICE_RE.search(line) else 0.0
    score -= index * 0.01  # em empate, preserva a primeira linha útil
    return score


def select_product_line(text: str) -> Optional[str]:
    """Seleciona a linha que mais se parece com o nome do produto.

    Mensagens de grupos frequentemente começam com slogan, chamada ou emoji.
    A seleção é deliberadamente conservadora e nunca combina linhas distintas.
    """
    candidates = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not candidates:
        return None
    if _COUPON_TITLE_RE.search(normalize_text(candidates[0])):
        return candidates[0]
    ranked = [(_candidate_score(line, index), line) for index, line in enumerate(candidates)]
    score, line = max(ranked, key=lambda item: item[0])
    return line if score != float("-inf") else candidates[0]


def has_multiple_product_offers(text: str) -> bool:
    """Detecta listas em que cada linha anuncia um produto e um preço.

    Duas formas de pagamento para o mesmo item ("por", "PIX", "ou no
    cartão") não contam como produtos diferentes.
    """
    product_price_lines = 0
    total_price_lines = 0
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or not _PRICE_RE.search(line):
            continue
        total_price_lines += 1
        normalized = normalize_text(line)
        if _PAYMENT_LINE_RE.search(_strip_leading_symbols(line)) or _NON_TITLE_RE.search(normalized):
            continue
        before_price = _PRICE_RE.split(normalized, maxsplit=1)[0]
        if len(re.findall(r"[a-z]{2,}", before_price)) >= 2:
            product_price_lines += 1

    return product_price_lines >= 2 or (product_price_lines >= 1 and total_price_lines >= 3)
