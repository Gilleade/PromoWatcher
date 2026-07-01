import asyncio
from enum import Enum
from typing import NamedTuple, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "tag", "ascsubtag", "linkCode", "camp", "creative", "ref", "ref_",
    "psc", "smid", "sprefix", "crid", "keywords", "qid",
}


class LinkStatus(str, Enum):
    CLEANED = "CLEANED"
    RESOLVED = "RESOLVED"
    ORIGINAL_FALLBACK = "ORIGINAL_FALLBACK"
    MULTIPLE_LINKS = "MULTIPLE_LINKS"
    NO_LINK = "NO_LINK"
    INTERMEDIATE_PAGE = "INTERMEDIATE_PAGE"
    ERROR_RESOLVING = "ERROR_RESOLVING"


class LinkResult(NamedTuple):
    url: str
    status: LinkStatus
    store_domain: Optional[str] = None


def clean_url(url: str) -> str:
    """Remove parâmetros de tracking/afiliado. Conservador: se algo der
    errado, retorna a URL original sem alterações."""
    try:
        parts = urlsplit(url)
        query_pairs = parse_qsl(parts.query, keep_blank_values=True)
        filtered = [(k, v) for k, v in query_pairs if k not in _TRACKING_PARAMS]
        new_query = urlencode(filtered)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
    except Exception:
        return url


def _domain_of(url: str) -> Optional[str]:
    try:
        return urlsplit(url).netloc or None
    except Exception:
        return None


def resolve_url_sync(url: str, timeout: float = 5.0) -> LinkResult:
    """Segue redirecionamentos com timeout curto. Nunca lança exceção:
    em qualquer falha, cai no fallback com a URL original preservada."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        final_url = response.url
        if response.status_code >= 400:
            # HEAD pode não ser suportado por alguns servidores; tenta GET leve
            response = requests.get(url, allow_redirects=True, timeout=timeout, stream=True)
            final_url = response.url
            response.close()

        cleaned = clean_url(final_url)
        status = LinkStatus.CLEANED if cleaned != final_url else LinkStatus.RESOLVED
        return LinkResult(url=cleaned, status=status, store_domain=_domain_of(cleaned))
    except requests.exceptions.Timeout:
        return LinkResult(url=url, status=LinkStatus.ERROR_RESOLVING, store_domain=_domain_of(url))
    except requests.exceptions.RequestException:
        return LinkResult(url=url, status=LinkStatus.ERROR_RESOLVING, store_domain=_domain_of(url))
    except Exception:
        return LinkResult(url=url, status=LinkStatus.ORIGINAL_FALLBACK, store_domain=_domain_of(url))


async def resolve_url_async(url: str, *, loop: Optional[asyncio.AbstractEventLoop] = None,
                             executor=None, timeout: float = 5.0) -> LinkResult:
    loop = loop or asyncio.get_event_loop()
    return await loop.run_in_executor(executor, resolve_url_sync, url, timeout)


def resolve_links(links: list) -> LinkResult:
    """Decide o link principal a partir de uma lista extraída da mensagem,
    seguindo a regra de fallback obrigatória (nunca descarta a promoção)."""
    if not links:
        return LinkResult(url="", status=LinkStatus.NO_LINK, store_domain=None)

    primary = links[0]
    result = resolve_url_sync(primary)
    if len(links) > 1 and result.status in (LinkStatus.CLEANED, LinkStatus.RESOLVED):
        return LinkResult(url=result.url, status=LinkStatus.MULTIPLE_LINKS, store_domain=result.store_domain)
    return result
