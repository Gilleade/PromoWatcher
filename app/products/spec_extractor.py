import re
from dataclasses import dataclass
from typing import Optional, Tuple

from app.parser.normalizer import normalize_text
from app.parser.product_text import select_product_line

# Mantida manualmente — cobre as marcas mais comuns em grupos de promoção BR.
# Cada marca canônica tem uma lista de termos-gatilho (a forma como as pessoas
# realmente escrevem no Telegram, nem sempre o nome oficial da marca —
# ex.: "Moto G56" sem escrever "Motorola").
BRAND_ALIASES = {
    "motorola": ["motorola", "moto"],
    "apple": ["iphone", "apple", "macbook", "ipad", "airpods", "airtag"],
    "samsung": ["samsung"],
    "xiaomi": ["xiaomi", "redmi", "poco"],
    "amd": ["amd", "ryzen"],
    "lg": ["lg"],
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
    "hp": ["hp"],
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
    "tablet": "Tablet",
    "smartwatch": "Smartwatch",
    "tracker": "Rastreador",
    "notebook": "Notebook",
    "console": "Console",
    "tv": "TV",
    "fone": "Fone de Ouvido",
    "caixa_som": "Áudio",
    "monitor": "Monitor",
    "teclado": "Teclado",
    "mouse": "Mouse",
    "controle": "Controle",
    "acessorio": "Acessório",
    "placa_mae": "Placa-mãe",
    "placa_video": "Placa de Vídeo",
    "processador": "Processador",
    "impressora": "Impressora",
    "componente": "Componente",
}

# A ordem é intencional: termos específicos vencem menções incidentais como
# "iPhone" na descrição de um AirTag ou "PS5" em um suporte para controle.
CATEGORY_KEYWORDS = {
    "tracker": ["airtag", "rastreador gps", "rastreador bluetooth", "localizador"],
    "tablet": ["tablet", "ipad", "galaxy tab"],
    "smartwatch": ["smartwatch", "smart watch", "relogio inteligente", "apple watch", "galaxy watch"],
    "acessorio": ["suporte para controle", "base para controle", "carregador para controle"],
    "placa_mae": ["placa mae", "placas mae", "motherboard", "mobo"],
    "placa_video": ["placa de video", "geforce", "radeon", " gpu "],
    "processador": ["processador", "ryzen", "core i3", "core i5", "core i7", "core i9"],
    "impressora": ["impressora", "multifuncional"],
    "caixa_som": ["caixa de som", "soundbar", "partybox"],
    "componente": ["fans magneticas", "fan magnetica", "kit de fans", "cooler"],
    "smartphone": [
        "celular", "smartphone", "iphone", "moto g", "moto e", "redmi", "poco",
        "galaxy a", "galaxy s", "galaxy m", "galaxy z",
    ],
    "notebook": ["notebook", "laptop", "macbook", "ultrabook"],
    "console": ["playstation", "ps5", "ps4", "xbox", "nintendo switch", "console"],
    "tv": ["smart tv", "televisao"],
    "fone": ["fone de ouvido", "headset", "earbud", "airpods", "fone bluetooth", "over ear"],
    "monitor": ["monitor gamer", "monitor curvo", "monitor"],
    "teclado": ["teclado mecanico", "teclado gamer", "teclado"],
    "mouse": ["mouse gamer", "mouse sem fio", "mouse"],
    "controle": ["controle sem fio", "controle gamer", "gamepad"],
}

_STORAGE_RAM_COMBINED_RE = re.compile(r"(\d{1,4})\s*/\s*(\d{1,4})\s*gb")
_CAPACITY_RE = re.compile(r"(?P<value>\d{1,4})\s*(?P<unit>tb|gb)\b")
_RAM_AFTER_RE = re.compile(r"(\d{1,3})\s*gb\s*(?:de\s*)?(?:ram|ddr\d?)\b")
_RAM_BEFORE_RE = re.compile(r"\bram\s*(?:de\s*)?(\d{1,3})\s*gb\b")
_STORAGE_CONTEXT_RE = re.compile(r"\b(?:ssd|hd|armazenamento|rom)\s*(?:de\s*)?(\d{1,4})\s*(tb|gb)\b")
_STORAGE_AFTER_RE = re.compile(r"(\d{1,4})\s*(tb|gb)\s*(?:de\s*)?(?:ssd|hd|armazenamento|rom)\b")
_VRAM_CONTEXT_RE = re.compile(r"\b(?:vram|gddr\d?)\b")
_YEAR_RE = re.compile(r"\b(20[0-3]\d)\b")
_CUTOFF_RE = re.compile(
    r"(r\$|\d+\s*/\s*\d+\s*gb|\d+\s*(?:tb|gb)|\bpor\b|\ba partir\b|"
    r"\bapenas\b|\bsomente\b|\bcom cupom\b|\blancado\b|\boriginal\b|"
    r"\bcom\b|\bsem fio\b|\bbluetooth\b)"
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


def _bounded_pattern(term: str) -> re.Pattern:
    clean = term.strip()
    return re.compile(rf"(?<![a-z0-9]){re.escape(clean)}(?![a-z0-9])")


def _find_brand(normalized_text: str, category: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """Retorna a marca e o gatilho usando limites reais de palavra."""
    best: Optional[Tuple[int, str, str]] = None
    for canonical, triggers in BRAND_ALIASES.items():
        for trigger in triggers:
            match = _bounded_pattern(trigger).search(normalized_text)
            if match and (best is None or match.start() < best[0]):
                best = (match.start(), canonical, trigger.strip())

    # "Galaxy" só implica Samsung quando a categoria também confirma que é
    # uma família de dispositivo Samsung; fans "Galaxy V2" não são Samsung.
    if category in {"smartphone", "tablet", "smartwatch"}:
        galaxy = _bounded_pattern("galaxy").search(normalized_text)
        if galaxy and (best is None or galaxy.start() < best[0]):
            best = (galaxy.start(), "samsung", "galaxy")

    return (best[1], best[2]) if best else (None, None)


def _find_category(normalized_text: str) -> Optional[str]:
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword.strip() in normalized_text for keyword in keywords):
            return category
    if re.search(r"\bgalaxy\s+[asmz]\d{2,}\b", normalized_text):
        return "smartphone"
    return None


def _capacity_to_gb(value: str, unit: str) -> int:
    amount = int(value)
    return amount * 1024 if unit == "tb" else amount


def _extract_storage_and_ram(normalized_text: str) -> Tuple[Optional[int], Optional[int]]:
    combined = _STORAGE_RAM_COMBINED_RE.search(normalized_text)
    if combined:
        a, b = int(combined.group(1)), int(combined.group(2))
        ram, storage = (a, b) if a <= b else (b, a)
        return storage, ram

    ram: Optional[int] = None
    ram_match = _RAM_AFTER_RE.search(normalized_text) or _RAM_BEFORE_RE.search(normalized_text)
    if ram_match:
        ram = int(ram_match.group(1))

    storage: Optional[int] = None
    storage_match = _STORAGE_CONTEXT_RE.search(normalized_text)
    if storage_match:
        storage = _capacity_to_gb(storage_match.group(1), storage_match.group(2))
    if storage is None:
        storage_match = _STORAGE_AFTER_RE.search(normalized_text)
        if storage_match:
            storage = _capacity_to_gb(storage_match.group(1), storage_match.group(2))

    if storage is None:
        for match in _CAPACITY_RE.finditer(normalized_text):
            around = normalized_text[max(0, match.start() - 12):match.end() + 12]
            if _VRAM_CONTEXT_RE.search(around):
                continue
            value = _capacity_to_gb(match.group("value"), match.group("unit"))
            if value >= 32:
                storage = value
                break

    return storage, ram


_PRODUCT_FAMILY_TRIGGERS = {
    "iphone", "ipad", "airpods", "airtag", "macbook", "playstation",
    "ps3", "ps4", "ps5", "xbox", "galaxy", "ryzen",
}
_MODEL_STOP_WORDS = {
    "amd", "intel", "preto", "branco", "azul", "bivolt", "novo", "nova",
    "wifi", "usb", "tela",
}


def _extract_model(normalized_text: str, matched_trigger: Optional[str]) -> Optional[str]:
    if not matched_trigger:
        return None
    match = _bounded_pattern(matched_trigger).search(normalized_text)
    if not match:
        return None

    after = normalized_text[match.end():].strip()
    cutoff = _CUTOFF_RE.search(after)
    model_part = after[:cutoff.start()] if cutoff else after[:80]
    model_part = re.sub(r"[^a-z0-9+./ ]+", " ", model_part)
    words = []
    for word in model_part.split():
        if word in _MODEL_STOP_WORDS:
            break
        words.append(word)
        if len(words) == 6:
            break

    if matched_trigger in _PRODUCT_FAMILY_TRIGGERS:
        words.insert(0, matched_trigger)
    return " ".join(words).strip() or None


def extract_specs(text: str) -> ExtractedSpecs:
    """Extração determinística de marca/modelo/RAM/armazenamento/ano/categoria
    a partir do texto bruto da mensagem. Nunca lança exceção — na ausência de
    sinais claros, os campos ficam None e completeness_confidence fica baixo,
    empurrando a decisão para a camada de matching/Ollama."""
    text = text or ""
    normalized_full = normalize_text(text)
    product_line = select_product_line(text) or text
    normalized_product = normalize_text(product_line)

    category = _find_category(normalized_product) or _find_category(normalized_full)
    brand, matched_trigger = _find_brand(normalized_product, category)
    if brand is None:
        brand, matched_trigger = _find_brand(normalized_full, category)

    storage_gb, ram_gb = _extract_storage_and_ram(normalized_full)
    model = _extract_model(normalized_product, matched_trigger)

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
