import re
from dataclasses import dataclass
from typing import Optional, Tuple

from app.parser.normalizer import normalize_text

# Mantida manualmente — cobre as marcas mais comuns em grupos de promoção BR.
# Cada marca canônica tem uma lista de termos-gatilho (a forma como as pessoas
# realmente escrevem no Telegram, nem sempre o nome oficial da marca —
# ex.: "Moto G56" sem escrever "Motorola").
BRAND_ALIASES = {
    "motorola": ["motorola", "moto "],
    "apple": ["iphone", "apple", "macbook", "ipad", "airpods"],
    "samsung": ["samsung", "galaxy"],
    "xiaomi": ["xiaomi", "redmi", "poco"],
    "lg": ["lg "],
    "asus": ["asus"],
    "acer": ["acer"],
    "lenovo": ["lenovo"],
    "dell": ["dell"],
    "sony": ["sony", "playstation", "ps5", "ps4", "ps3"],
    "jbl": ["jbl"],
    "philips": ["philips"],
    "multilaser": ["multilaser"],
    "positivo": ["positivo"],
    "realme": ["realme"],
    "nokia": ["nokia"],
    "huawei": ["huawei"],
    "hp": ["hp "],
    "logitech": ["logitech"],
    "razer": ["razer"],
    "redragon": ["redragon"],
    "corsair": ["corsair"],
    "aoc": ["aoc"],
    "gamesir": ["gamesir"],
    "microsoft": ["xbox"],
    # "switch" sozinho é gatilho demais (switch mecânico de teclado, switch de
    # rede etc.) — já causou um produto real virar "Nintendo" a partir de um
    # teclado gamer com "Cherry MX Red Switch Hot-Swappable" no texto. Exige
    # a frase completa "nintendo switch".
    "nintendo": ["nintendo"],
}

# Prefixo de tipo de produto adicionado no início do canonical_title (ex.:
# "Notebook Asus Tuf A15 ..." em vez de só "Asus Tuf A15 ...") — sem isso o
# título não deixa claro o que é o produto quando a marca/modelo não é
# autoexplicativa.
CATEGORY_TITLE_PREFIX = {
    "smartphone": "Celular",
    "notebook": "Notebook",
    "console": "Console",
    "tv": "TV",
    "fone": "Fone de Ouvido",
    "monitor": "Monitor",
    "teclado": "Teclado",
    "mouse": "Mouse",
    "controle": "Controle",
}

CATEGORY_KEYWORDS = {
    "smartphone": ["celular", "smartphone", "iphone", "galaxy", "moto g", "moto e", "redmi", "poco"],
    "notebook": ["notebook", "laptop", "macbook", "ultrabook"],
    "console": ["playstation", "ps5", "ps4", "xbox", "nintendo switch", "console"],
    "tv": ["smart tv", " tv ", "televisao"],
    "fone": ["fone de ouvido", "headset", "earbud", "airpods", "fone bluetooth"],
    "monitor": ["monitor gamer", "monitor curvo", "monitor "],
    "teclado": ["teclado mecanico", "teclado gamer", "teclado "],
    "mouse": ["mouse gamer", "mouse sem fio", "mouse "],
    "controle": ["controle sem fio", "controle gamer", "gamepad"],
}

_STORAGE_RAM_COMBINED_RE = re.compile(r"(\d{1,4})\s*/\s*(\d{1,4})\s*gb")
_SINGLE_GB_RE = re.compile(r"(\d{1,4})\s*gb")
_YEAR_RE = re.compile(r"\b(20[0-3]\d)\b")
_CUTOFF_RE = re.compile(
    r"(r\$|\d+\s*/\s*\d+\s*gb|\d+\s*gb|\bpor\b|\ba partir\b|\bapenas\b|\bsomente\b|\bcom cupom\b)"
)


@dataclass
class ExtractedSpecs:
    brand: Optional[str] = None
    model: Optional[str] = None
    storage_gb: Optional[int] = None
    ram_gb: Optional[int] = None
    release_year: Optional[int] = None
    category: Optional[str] = None
    variant_label: Optional[str] = None
    completeness_confidence: float = 0.0


def _find_brand(normalized_text: str) -> Tuple[Optional[str], Optional[str]]:
    """Retorna (marca_canonica, termo_que_casou). O termo que casou é o que
    realmente aparece no texto (ex.: "moto ") e é usado depois para localizar
    onde o nome do modelo começa — a marca canônica (ex.: "motorola") pode
    nunca aparecer literalmente na mensagem. Quando a marca aparece mais de
    uma vez (ex.: "Moto G56 ... direto da Motorola"), usa a ocorrência mais
    cedo no texto — é ali que o nome do modelo normalmente está."""
    best: Optional[Tuple[int, str, str]] = None  # (index, canonical, trigger)
    for canonical, triggers in BRAND_ALIASES.items():
        for trigger in triggers:
            idx = normalized_text.find(trigger)
            if idx != -1 and (best is None or idx < best[0]):
                best = (idx, canonical, trigger)
    if best is None:
        return None, None
    return best[1], best[2]


def _find_category(normalized_text: str) -> Optional[str]:
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized_text:
                return category
    return None


def _extract_storage_and_ram(normalized_text: str) -> Tuple[Optional[int], Optional[int]]:
    combined = _STORAGE_RAM_COMBINED_RE.search(normalized_text)
    if combined:
        a, b = int(combined.group(1)), int(combined.group(2))
        # padrão comum BR "6/128GB" = RAM/Armazenamento (o menor dos dois é a RAM)
        ram, storage = (a, b) if a <= b else (b, a)
        return storage, ram

    storage: Optional[int] = None
    ram: Optional[int] = None
    for match in _SINGLE_GB_RE.finditer(normalized_text):
        value = int(match.group(1))
        if value >= 32 and storage is None:
            storage = value
        elif value <= 16 and ram is None:
            ram = value
    return storage, ram


def _extract_model(normalized_text: str, matched_trigger: Optional[str]) -> Optional[str]:
    if not matched_trigger:
        return None
    idx = normalized_text.find(matched_trigger)
    if idx == -1:
        return None
    after = normalized_text[idx + len(matched_trigger):].strip()
    cutoff = _CUTOFF_RE.search(after)
    model_part = after[:cutoff.start()] if cutoff else after[:40]
    model_part = model_part.strip(" -,:|")
    words = model_part.split()[:4]
    return " ".join(words) if words else None


def extract_specs(text: str) -> ExtractedSpecs:
    """Extração determinística de marca/modelo/RAM/armazenamento/ano/categoria
    a partir do texto bruto da mensagem. Nunca lança exceção — na ausência de
    sinais claros, os campos ficam None e completeness_confidence fica baixo,
    empurrando a decisão para a camada de matching/Ollama."""
    text = text or ""
    normalized = normalize_text(text)

    brand, matched_trigger = _find_brand(normalized)
    category = _find_category(normalized)
    storage_gb, ram_gb = _extract_storage_and_ram(normalized)
    model = _extract_model(normalized, matched_trigger)

    year_match = _YEAR_RE.search(text)
    release_year = int(year_match.group(1)) if year_match else None

    found_fields = sum(f is not None for f in (brand, model, storage_gb))
    completeness_confidence = found_fields / 3.0

    label_parts = []
    if storage_gb:
        label_parts.append(f"{storage_gb}GB")
    if ram_gb:
        label_parts.append(f"{ram_gb}GB RAM")
    variant_label = " ".join(label_parts) if label_parts else None

    return ExtractedSpecs(
        brand=brand,
        model=model,
        storage_gb=storage_gb,
        ram_gb=ram_gb,
        release_year=release_year,
        category=category,
        variant_label=variant_label,
        completeness_confidence=completeness_confidence,
    )


def build_variant_key(brand: Optional[str], model: Optional[str],
                       storage_gb: Optional[int], ram_gb: Optional[int]) -> str:
    """Fingerprint normalizado usado tanto no armazenamento (products.variant_key)
    quanto na busca de match exato — specs diferentes nunca geram a mesma chave."""
    b = (brand or "?").strip().lower()
    m = (model or "?").strip().lower()
    s = str(storage_gb) if storage_gb is not None else "?"
    r = str(ram_gb) if ram_gb is not None else "?"
    return f"{b}|{m}|{s}|{r}"
