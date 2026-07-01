from decimal import Decimal

from app.parser.price_parser import extract_coupon, extract_price, extract_price_range, extract_prices


def test_extract_price_simple_rs_format():
    assert extract_price("Notebook por R$ 4.299,00") == Decimal("4299.00")


def test_extract_price_without_space():
    assert extract_price("R$4299,00 no site") == Decimal("4299.00")


def test_extract_price_reais_suffix():
    assert extract_price("Custa 4.299,00 reais") == Decimal("4299.00")


def test_extract_price_no_price_returns_none():
    assert extract_price("Sem preço nenhum aqui") is None


def test_extract_price_range_de_por():
    old_price, price = extract_price_range("De R$ 5.000,00 por R$ 4.299,00")
    assert old_price == Decimal("5000.00")
    assert price == Decimal("4299.00")


def test_extract_price_range_single_price():
    old_price, price = extract_price_range("Só R$ 100,00")
    assert old_price is None
    assert price == Decimal("100.00")


def test_extract_prices_multiple_in_order():
    prices = extract_prices("De R$ 100,00 por R$ 80,00")
    assert prices == [Decimal("100.00"), Decimal("80.00")]


def test_extract_coupon():
    assert extract_coupon("Use o cupom NOTE600 para desconto") == "NOTE600"


def test_extract_coupon_none():
    assert extract_coupon("Sem cupom aqui") is None
