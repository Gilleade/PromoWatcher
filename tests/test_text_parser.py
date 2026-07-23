from decimal import Decimal

from app.parser.text_parser import parse_message


def test_parse_message_fills_installment_fields():
    text = (
        "Monitor AOC 22\" 120Hz 1ms\n\n"
        "DE R$ 499,00\n"
        "POR R$ 420,00\n"
        "Em até 8x de R$ 52,50 sem juros"
    )
    parsed = parse_message(text)
    assert parsed.old_price == Decimal("499.00")
    assert parsed.price == Decimal("420.00")
    assert parsed.installment_count == 8
    assert parsed.installment_price == Decimal("52.50")
    assert parsed.installment_no_interest is True


def test_parse_message_without_installment_leaves_fields_none():
    parsed = parse_message("Notebook por R$ 2.999,00 à vista")
    assert parsed.installment_count is None
    assert parsed.installment_price is None
    assert parsed.installment_no_interest is None
