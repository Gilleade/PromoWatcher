import re

from unidecode import unidecode


def normalize_text(text: str, *, accent_insensitive: bool = True,
                    normalize_spaces_dashes: bool = True, case_insensitive: bool = True) -> str:
    t = text
    if accent_insensitive:
        t = unidecode(t)
    if normalize_spaces_dashes:
        t = t.replace("-", " ")
        t = re.sub(r"\s+", " ", t)
    if case_insensitive:
        t = t.lower()
    return t.strip()
