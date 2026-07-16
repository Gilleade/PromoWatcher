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


def test_price_followed_by_off_is_not_a_product_price():
    # "R$20 OFF" é o valor de um cupom de desconto, não o preço de um item
    assert extract_prices("Cupom de R$20 OFF válido em todo o site") == []
    assert extract_price("Cupom de R$20 OFF válido em todo o site") is None


def test_price_followed_by_off_does_not_hide_a_real_price_earlier():
    prices = extract_prices("Notebook por R$ 2.999,00, use o cupom de R$50 OFF")
    assert prices == [Decimal("2999.00")]


def test_installment_value_is_not_a_product_price():
    # "8x de R$ 52,50" é o valor da parcela, não o preço à vista — bug real
    # observado em produção: essa mensagem gravou R$52,50 como preço final
    # em vez de R$420,00 (o "POR R$ ...").
    text = (
        "Monitor AOC 22\" 120Hz 1ms\n\n"
        "DE R$ 499,00\n"
        "POR R$ 420,00\n"
        "Em até 8x de R$ 52,50 sem juros"
    )
    old_price, price = extract_price_range(text)
    assert old_price == Decimal("499.00")
    assert price == Decimal("420.00")


def test_installment_value_excluded_without_de():
    prices = extract_prices("Só R$ 100,00 ou 10x R$ 10,00")
    assert prices == [Decimal("100.00")]
