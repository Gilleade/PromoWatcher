from app.parser.link_extractor import extract_links


def test_extract_single_https_link():
    links = extract_links("Confira: https://www.amazon.com.br/produto/xyz")
    assert links == ["https://www.amazon.com.br/produto/xyz"]


def test_extract_multiple_links_preserves_order():
    text = "Link 1: https://a.com/1 e depois https://b.com/2"
    links = extract_links(text)
    assert links == ["https://a.com/1", "https://b.com/2"]


def test_extract_bare_shortener_amzn_to():
    links = extract_links("Promoção aqui: amzn.to/3xYz9")
    assert links == ["https://amzn.to/3xYz9"]


def test_extract_no_links():
    assert extract_links("Texto sem nenhum link") == []


def test_extract_strips_trailing_punctuation():
    links = extract_links("Veja (https://site.com/produto).")
    assert links == ["https://site.com/produto"]
