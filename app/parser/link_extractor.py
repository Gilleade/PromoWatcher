import re
from typing import List

_URL_WITH_SCHEME = re.compile(r"https?://[^\s<>\"']+")

_BARE_SHORTENERS = re.compile(
    r"\b(?:amzn\.to|meli\.la|s\.shopee\.com\.br|link\.amazon\.com\.br|"
    r"aoferta\.net|bit\.ly|tinyurl\.com)/[^\s<>\"']+",
    re.IGNORECASE,
)

_TRAILING_PUNCTUATION = ".,;)]}'\""


def extract_links(text: str) -> List[str]:
    if not text:
        return []

    found: List[str] = []

    for m in _URL_WITH_SCHEME.finditer(text):
        found.append(m.group(0).rstrip(_TRAILING_PUNCTUATION))

    for m in _BARE_SHORTENERS.finditer(text):
        candidate = m.group(0).rstrip(_TRAILING_PUNCTUATION)
        if not any(candidate in existing for existing in found):
            found.append("https://" + candidate)

    seen = set()
    result = []
    for url in found:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result
