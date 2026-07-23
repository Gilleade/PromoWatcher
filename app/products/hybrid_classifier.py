"""Validação híbrida de extração determinística e sugestão da IA.

Esta camada produz diagnóstico para o modo sombra e nunca grava produto,
associação ou categoria por conta própria.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, Tuple

from app.parser.normalizer import normalize_text
from app.products.ollama_client import OllamaExtractionResult
from app.products.taxonomy_catalog import CATALOG_VERSION, canonical_category


@dataclass(frozen=True)
class HybridClassification:
    status: str
    deterministic_category: Optional[str]
    ai_category: Optional[str]
    selected_category: Optional[str]
    validated_ai_fields: Dict[str, Any] = field(default_factory=dict)
    rejected_ai_fields: Dict[str, str] = field(default_factory=dict)
    reasons: Tuple[str, ...] = ()
    catalog_version: str = CATALOG_VERSION

    def as_dict(self) -> dict:
        return asdict(self)


def _string_has_evidence(raw_text: str, value: str) -> bool:
    text = normalize_text(raw_text)
    normalized_value = normalize_text(value)
    if not normalized_value:
        return False
    if normalized_value in text:
        return True
    tokens = [token for token in normalized_value.split() if len(token) >= 2]
    return len(tokens) >= 2 and all(
        re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text)
        for token in tokens
    )


def _number_has_evidence(raw_text: str, value: int, field_name: str) -> bool:
    text = normalize_text(raw_text)
    number = re.escape(str(value))
    if field_name == "ram_gb":
        patterns = (
            rf"\b{number}\s*gb\s*(?:de\s*)?(?:ram|ddr\d?)\b",
            rf"\b(?:ram|ddr\d?)\s*(?:de\s*)?{number}\s*gb\b",
        )
    elif field_name == "storage_gb":
        patterns = (
            rf"\b(?:ssd|hd|armazenamento|rom)\s*(?:de\s*)?{number}\s*gb\b",
            rf"\b{number}\s*gb\s*(?:de\s*)?(?:ssd|hd|armazenamento|rom)\b",
        )
    else:
        patterns = (rf"(?<!\d){number}(?!\d)",)
    return any(re.search(pattern, text) for pattern in patterns)


def _field_has_evidence(raw_text: str, field_name: str, value: Any) -> bool:
    if isinstance(value, str):
        return _string_has_evidence(raw_text, value)
    if isinstance(value, int):
        return _number_has_evidence(raw_text, value, field_name)
    return False


def classify_hybrid(
    *, deterministic_specs: dict, ai_extraction: Optional[OllamaExtractionResult], raw_text: str,
) -> HybridClassification:
    """Compara as duas fontes sem promover sugestões não comprovadas."""
    deterministic_category = canonical_category(deterministic_specs.get("category"))
    ai_category = None
    validated: Dict[str, Any] = {}
    rejected: Dict[str, str] = {}
    reasons = []

    if ai_extraction is not None and ai_extraction.ok:
        raw_ai_category = ai_extraction.category
        ai_category = canonical_category(raw_ai_category)
        if raw_ai_category and ai_category is None:
            rejected["category"] = "categoria fora do catálogo oficial"

        for field_name in ("brand", "model", "storage_gb", "ram_gb", "release_year"):
            value = getattr(ai_extraction, field_name)
            if value is None or deterministic_specs.get(field_name) is not None:
                continue
            if _field_has_evidence(raw_text, field_name, value):
                validated[field_name] = value
            else:
                rejected[field_name] = "sem evidência no texto da promoção"

    if deterministic_category and ai_category:
        if deterministic_category == ai_category:
            status = "CONFIRMED"
            selected_category = deterministic_category
            reasons.append("regra determinística e IA concordam")
        else:
            status = "CONFLICT"
            selected_category = deterministic_category
            rejected["category"] = "conflita com a regra determinística"
            reasons.append("categoria determinística preservada")
    elif deterministic_category:
        status = "DETERMINISTIC_ONLY"
        selected_category = deterministic_category
        reasons.append("somente a regra determinística definiu categoria")
    elif ai_category:
        status = "AI_CANDIDATE"
        selected_category = None
        reasons.append("categoria da IA aguarda validação; não foi promovida")
    else:
        status = "UNRESOLVED"
        selected_category = None
        reasons.append("nenhuma categoria canônica comprovada")

    return HybridClassification(
        status=status,
        deterministic_category=deterministic_category,
        ai_category=ai_category,
        selected_category=selected_category,
        validated_ai_fields=validated,
        rejected_ai_fields=rejected,
        reasons=tuple(reasons),
    )
