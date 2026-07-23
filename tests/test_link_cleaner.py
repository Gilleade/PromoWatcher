from unittest.mock import Mock, patch

import requests

from app.parser.link_resolver import LinkStatus, clean_url, resolve_links, resolve_url_sync


def test_clean_url_removes_tracking_params():
    dirty = "https://www.amazon.com.br/produto?tag=afiliado123&psc=1&utm_source=telegram"
    cleaned = clean_url(dirty)
    assert "tag=" not in cleaned
    assert "psc=" not in cleaned
    assert "utm_source=" not in cleaned
    assert cleaned.startswith("https://www.amazon.com.br/produto")


def test_clean_url_keeps_non_tracking_params():
    url = "https://loja.com/produto?id=123&cor=azul"
    cleaned = clean_url(url)
    assert "id=123" in cleaned
    assert "cor=azul" in cleaned


def test_clean_url_no_params_unchanged():
    url = "https://loja.com/produto"
    assert clean_url(url) == url


def test_resolve_url_sync_success_returns_cleaned_status():
    fake_response = Mock(status_code=200, url="https://loja.com/produto?tag=xyz")
    with patch("app.parser.link_resolver.requests.head", return_value=fake_response):
        result = resolve_url_sync("https://short.ly/abc")
    assert result.status == LinkStatus.CLEANED
    assert "tag=" not in result.url


def test_resolve_url_sync_timeout_falls_back_to_original():
    with patch("app.parser.link_resolver.requests.head", side_effect=requests.exceptions.Timeout):
        result = resolve_url_sync("https://short.ly/broken", timeout=1)
    assert result.status == LinkStatus.ERROR_RESOLVING
    assert result.url == "https://short.ly/broken"


def test_resolve_url_sync_connection_error_falls_back_to_original():
    with patch("app.parser.link_resolver.requests.head",
               side_effect=requests.exceptions.ConnectionError):
        result = resolve_url_sync("https://short.ly/broken")
    assert result.status == LinkStatus.ERROR_RESOLVING
    assert result.url == "https://short.ly/broken"


def test_resolve_links_no_link_returns_no_link_status():
    result = resolve_links([])
    assert result.status == LinkStatus.NO_LINK
    assert result.url == ""


def test_resolve_links_multiple_links_marks_multiple():
    fake_response = Mock(status_code=200, url="https://loja.com/produto")
    with patch("app.parser.link_resolver.requests.head", return_value=fake_response):
        result = resolve_links(["https://loja.com/1", "https://loja.com/2"])
    assert result.status == LinkStatus.MULTIPLE_LINKS


def test_resolve_never_raises_even_on_unexpected_exception():
    with patch("app.parser.link_resolver.requests.head", side_effect=RuntimeError("boom")):
        result = resolve_url_sync("https://short.ly/weird")
    assert result.status in (LinkStatus.ERROR_RESOLVING, LinkStatus.ORIGINAL_FALLBACK)
    assert result.url == "https://short.ly/weird"
