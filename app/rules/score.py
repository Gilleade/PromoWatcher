from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from app.rules.alert_matcher import MatchResult

BUG_TERMS = ["bug", "provavel bug", "possivel bug", "preco errado", "erro de preco"]

KNOWN_STORE_DOMAINS = {
    "amazon.com.br", "amazon.com", "mercadolivre.com.br", "magazineluiza.com.br",
    "magalu.com.br", "kabum.com.br", "shopee.com.br", "casasbahia.com.br",
    "americanas.com.br", "pichau.com.br",
}


@dataclass
class ScoreResult:
    score: int
    reason: str


def _contains_bug_term(normalized_text: str) -> bool:
    return any(term in normalized_text for term in BUG_TERMS)


def _is_known_store(store_domain: Optional[str]) -> bool:
    if not store_domain:
        return False
    return any(domain in store_domain for domain in KNOWN_STORE_DOMAINS)


def compute_score(*, normalized_text: str, price: Optional[Decimal], match_result: MatchResult,
                   store_domain: Optional[str] = None) -> ScoreResult:
    alert = match_result.alert
    points: List[str] = []
    total = 0

    if alert.required and set(match_result.matched_required) == set(alert.required):
        total += 40
        points.append("+40 todos os termos obrigatórios encontrados")

    if match_result.matched_any:
        total += 15
        points.append("+15 termo opcional encontrado")

    if alert.max_price is not None:
        if price is not None and float(price) <= alert.max_price:
            total += 20
            points.append("+20 preço abaixo do máximo definido")
        elif price is None:
            total -= 30
            points.append("-30 preço não identificado apesar de exigido pelo alerta")

    if _contains_bug_term(normalized_text):
        total += 15
        points.append("+15 contém termo de bug/preço errado")

    if _is_known_store(store_domain):
        total += 10
        points.append("+10 link de loja conhecida")

    if match_result.matched_excluded:
        total -= 50
        points.append(f"-50 contém termo bloqueado: {', '.join(match_result.matched_excluded)}")

    reason = "; ".join(points) if points else "Nenhum critério de pontuação aplicado."
    return ScoreResult(score=total, reason=reason)
