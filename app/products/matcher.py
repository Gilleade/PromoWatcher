import difflib
import re
import sqlite3
from dataclasses import dataclass, field
from typing import List, Optional

from app.database import find_product_by_variant_key, list_active_products
from app.products.spec_extractor import ExtractedSpecs, build_variant_key

AUTO_MATCH_THRESHOLD = 0.85
NEEDS_REVIEW_THRESHOLD = 0.55

DECISION_AUTO_MATCH = "AUTO_MATCH"
DECISION_AUTO_NEW = "AUTO_NEW"
DECISION_NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class MatchCandidate:
    product_id: int
    confidence: float
    reason: str


@dataclass
class MatchDecision:
    decision: str
    product_id: Optional[int] = None
    confidence: float = 0.0
    candidates: List[MatchCandidate] = field(default_factory=list)


# Códigos de modelo no padrão "letra(s)+2 ou mais dígitos" (g54, g55, a55...).
# Propositalmente NÃO casa com marcadores de rede como "5g"/"4g" (que começam
# com dígito) — só o "código do aparelho" em si.
_MODEL_CODE_RE = re.compile(r"\b[a-z]+\d{2,}\b")


def _model_similarity(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0

    codes_a = set(_MODEL_CODE_RE.findall(a))
    codes_b = set(_MODEL_CODE_RE.findall(b))
    if codes_a and codes_b and codes_a.isdisjoint(codes_b):
        # "g54" vs "g55": textualmente ~91% parecidos, mas são aparelhos
        # diferentes — similaridade de caractere pura erra feio nesse caso.
        return 0.0

    return difflib.SequenceMatcher(None, a, b).ratio()


def _score_candidate(specs: ExtractedSpecs, candidate: sqlite3.Row) -> Optional[float]:
    """None = descarta o candidato. Marca ou armazenamento diferentes (quando
    ambos conhecidos) nunca podem gerar match — specs diferentes são sempre
    produtos diferentes, essa regra não é negociável."""
    if specs.brand and candidate["brand"] and specs.brand != candidate["brand"]:
        return None
    if (specs.storage_gb is not None and candidate["storage_gb"] is not None
            and specs.storage_gb != candidate["storage_gb"]):
        return None

    score = 0.0
    if specs.brand and candidate["brand"] and specs.brand == candidate["brand"]:
        score += 0.30
    if specs.storage_gb is not None and specs.storage_gb == candidate["storage_gb"]:
        score += 0.20
    if specs.ram_gb is not None and specs.ram_gb == candidate["ram_gb"]:
        score += 0.10
    score += 0.40 * _model_similarity(specs.model, candidate["model"])
    return score


def find_candidates(conn: sqlite3.Connection, specs: ExtractedSpecs, limit: int = 5) -> List[MatchCandidate]:
    rows = list_active_products(conn, brand=specs.brand, category=specs.category)

    scored = []
    for row in rows:
        score = _score_candidate(specs, row)
        if score is None:
            continue
        reason = (
            f"marca={'ok' if specs.brand == row['brand'] else 'na'} "
            f"armazenamento={'ok' if specs.storage_gb == row['storage_gb'] else 'na'} "
            f"sim_modelo={_model_similarity(specs.model, row['model']):.2f}"
        )
        scored.append(MatchCandidate(product_id=row["id"], confidence=score, reason=reason))

    scored.sort(key=lambda c: c.confidence, reverse=True)
    return scored[:limit]


def match_product(conn: sqlite3.Connection, specs: ExtractedSpecs) -> MatchDecision:
    """Decide se a promoção pertence a um produto existente, deve criar um
    novo, ou precisa de revisão (humana ou via IA local, próxima etapa).
    Limiares propositalmente conservadores: um match errado funde histórico
    de dois produtos diferentes (difícil de desfazer); um produto duplicado
    se corrige com um clique na tela de admin."""
    has_minimum_identity = specs.brand is not None or specs.model is not None
    incomplete = specs.brand is None or specs.model is None

    if has_minimum_identity:
        variant_key = build_variant_key(specs.brand, specs.model, specs.storage_gb, specs.ram_gb)
        exact = find_product_by_variant_key(conn, variant_key)
        if exact:
            return MatchDecision(decision=DECISION_AUTO_MATCH, product_id=exact["id"], confidence=1.0)

    candidates = find_candidates(conn, specs)

    if not candidates:
        if incomplete:
            return MatchDecision(decision=DECISION_NEEDS_REVIEW, confidence=0.0)
        return MatchDecision(decision=DECISION_AUTO_NEW, confidence=0.0)

    best = candidates[0]

    if incomplete or best.confidence < AUTO_MATCH_THRESHOLD:
        if best.confidence >= NEEDS_REVIEW_THRESHOLD or incomplete:
            return MatchDecision(
                decision=DECISION_NEEDS_REVIEW, confidence=best.confidence, candidates=candidates,
            )
        return MatchDecision(decision=DECISION_AUTO_NEW, confidence=best.confidence, candidates=candidates)

    return MatchDecision(
        decision=DECISION_AUTO_MATCH, product_id=best.product_id,
        confidence=best.confidence, candidates=candidates,
    )
