"""Catálogo canônico e versionado de categorias de produto.

O módulo apenas descreve a taxonomia. A classificação produtiva continua no
extrator legado até que o classificador híbrido seja validado em modo sombra.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Optional, Tuple


CATALOG_VERSION = "1.0.0"
_CATALOG_PATH = Path(__file__).with_name("category_catalog.csv")
_VALID_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_VALID_PRIORITIES = {"HIGH", "MEDIUM", "LOW"}
_VALID_STATUSES = {"PROPOSED", "REVIEWED", "BLOCKED"}

# Categorias já persistidas pelo extrator atual. A tradução fica explícita e
# não é aplicada automaticamente nesta etapa para evitar mudanças retroativas.
LEGACY_CATEGORY_ALIASES: Mapping[str, str] = MappingProxyType({
    "smartphone": "smartphone",
    "tablet": "tablet",
    "smartwatch": "smartwatch",
    "tracker": "smart_home_network",
    "notebook": "notebook",
    "console": "console",
    "tv": "tv",
    "fone": "audio",
    "caixa_som": "audio",
    "monitor": "monitor",
    "teclado": "computer_peripheral",
    "mouse": "computer_peripheral",
    "controle": "computer_peripheral",
    "acessorio": "computer_peripheral",
    "placa_mae": "motherboard",
    "placa_video": "graphics_card",
    "processador": "processor",
    "impressora": "printer",
    "componente": "case_cooling",
})


class InvalidTaxonomyCatalog(ValueError):
    """Indica inconsistência no arquivo oficial de taxonomia."""


@dataclass(frozen=True)
class CategoryProfile:
    family: str
    category: str
    occurrences: int
    priority: str
    identity_fields: Tuple[str, ...]
    variant_fields: Tuple[str, ...]
    allowed_units: Tuple[str, ...]
    hard_conflicts: Tuple[str, ...]
    status: str


def _split(value: str, separator: str = ",") -> Tuple[str, ...]:
    return tuple(part.strip() for part in value.split(separator) if part.strip())


def _profile_from_row(row: Mapping[str, str], line_number: int) -> CategoryProfile:
    category = (row.get("category") or "").strip()
    family = (row.get("family") or "").strip()
    priority = (row.get("priority") or "").strip().upper()
    status = (row.get("status") or "").strip().upper()
    identity_fields = _split(row.get("identity_fields") or "")

    if not _VALID_NAME.fullmatch(category) or not _VALID_NAME.fullmatch(family):
        raise InvalidTaxonomyCatalog(f"linha {line_number}: família ou categoria inválida")
    if priority not in _VALID_PRIORITIES:
        raise InvalidTaxonomyCatalog(f"linha {line_number}: prioridade inválida: {priority}")
    if status not in _VALID_STATUSES:
        raise InvalidTaxonomyCatalog(f"linha {line_number}: status inválido: {status}")
    if not identity_fields:
        raise InvalidTaxonomyCatalog(f"linha {line_number}: identidade não pode ser vazia")
    try:
        occurrences = int(row.get("occurrences") or 0)
    except ValueError as exc:
        raise InvalidTaxonomyCatalog(f"linha {line_number}: ocorrências inválidas") from exc
    if occurrences < 0:
        raise InvalidTaxonomyCatalog(f"linha {line_number}: ocorrências negativas")

    return CategoryProfile(
        family=family,
        category=category,
        occurrences=occurrences,
        priority=priority,
        identity_fields=identity_fields,
        variant_fields=_split(row.get("variant_fields") or ""),
        allowed_units=_split(row.get("allowed_units") or "", ";"),
        hard_conflicts=_split(row.get("hard_conflicts") or "", ";"),
        status=status,
    )


@lru_cache(maxsize=1)
def load_category_catalog() -> Mapping[str, CategoryProfile]:
    """Carrega e valida o catálogo uma vez, expondo uma visão imutável."""
    profiles = {}
    with _CATALOG_PATH.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {
            "family", "category", "occurrences", "priority", "identity_fields",
            "variant_fields", "allowed_units", "hard_conflicts", "status",
        }
        if not reader.fieldnames or set(reader.fieldnames) != required:
            raise InvalidTaxonomyCatalog("cabeçalho do catálogo é inválido")
        for line_number, row in enumerate(reader, start=2):
            profile = _profile_from_row(row, line_number)
            if profile.category in profiles:
                raise InvalidTaxonomyCatalog(
                    f"linha {line_number}: categoria duplicada: {profile.category}"
                )
            profiles[profile.category] = profile
    if not profiles:
        raise InvalidTaxonomyCatalog("catálogo vazio")
    return MappingProxyType(profiles)


def canonical_category(category: Optional[str]) -> Optional[str]:
    """Resolve um nome legado; categorias canônicas válidas passam intactas."""
    if not category:
        return None
    normalized = category.strip().lower()
    if normalized in load_category_catalog():
        return normalized
    return LEGACY_CATEGORY_ALIASES.get(normalized)


def get_category_profile(category: Optional[str]) -> Optional[CategoryProfile]:
    canonical = canonical_category(category)
    return load_category_catalog().get(canonical) if canonical else None
