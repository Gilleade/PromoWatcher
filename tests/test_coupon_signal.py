from app.parser.coupon_signal import PRODUCT, COUPON, classify_message_kind, extract_discount_label
from app.parser.text_parser import parse_message


def test_message_with_price_is_product():
    parsed = parse_message("Motorola Moto G56 5G 256GB por R$ 1.093,90")
    assert classify_message_kind(parsed) == PRODUCT


def test_message_with_coupon_code_and_no_price_is_coupon():
    parsed = parse_message("Use o cupom BUG10 e ganhe desconto em toda a loja, sem produto especifico")
    assert classify_message_kind(parsed) == COUPON


def test_message_with_discount_label_and_no_price_is_coupon():
    parsed = parse_message("Cupom de R$20 OFF valido em todo o site, aproveita")
    assert classify_message_kind(parsed) == COUPON


def test_message_with_percent_discount_label_is_coupon():
    parsed = parse_message("Cupom Mercado Livre 30% OFF em compras acima de 69")
    assert classify_message_kind(parsed) == COUPON


def test_message_with_no_signal_defaults_to_product():
    parsed = parse_message("Promoção imperdível, corre que acaba!")
    assert classify_message_kind(parsed) == PRODUCT


def test_extract_discount_label_reais_off():
    assert extract_discount_label("Cupom de R$20 OFF valido em todo o site") == "R$20 OFF"


def test_extract_discount_label_percent_off():
    assert extract_discount_label("30% OFF em produtos selecionados") == "30% OFF"


def test_extract_discount_label_none_when_absent():
    assert extract_discount_label("Sem nenhum desconto mencionado aqui") is None


def test_extract_discount_label_empty_text():
    assert extract_discount_label("") is None
