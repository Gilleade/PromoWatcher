from decimal import Decimal

from app.parser.coupon_signal import COUPON, PRODUCT, classify_message_kind
from app.parser.price_parser import extract_coupon
from app.parser.text_parser import parse_message
from app.products.spec_extractor import extract_specs


def test_brand_aliases_respect_word_boundaries():
    assert extract_specs("Tênis Fila Racer Comet 2 por R$201").brand is None
    assert extract_specs("Esteira com motor 1.5HP Pico por R$883").brand is None
    assert extract_specs("Cupom IFPUBJLG para Ryzen 7 5700X por R$979").brand == "amd"


def test_galaxy_fans_are_not_samsung_smartphones():
    specs = extract_specs(
        "Kit 3 Fans Magnéticas Jungle Leopard Galaxy V2 ARGB 5V Reverse por R$189"
    )
    assert specs.brand is None
    assert specs.category == "componente"


def test_product_line_wins_over_slogan_for_model_extraction():
    specs = extract_specs(
        "JBL É TOP NÉ?!\n\nJBL Over-Ear Tune 530BT, Sem Fio\n\npor R$173"
    )
    assert specs.brand == "jbl"
    assert specs.category == "fone"
    assert specs.model == "over ear tune 530bt"


def test_specific_category_wins_over_incidental_device_mention():
    specs = extract_specs(
        "Apple AirTag Original - Rastreador GPS Localização iPhone por R$138"
    )
    assert specs.brand == "apple"
    assert specs.category == "tracker"
    assert specs.model == "airtag"


def test_vram_is_not_treated_as_system_ram_or_storage():
    specs = extract_specs("Placa de Vídeo Radeon RX 7600 8GB GDDR6 por R$1.799")
    assert specs.category == "placa_video"
    assert specs.storage_gb is None
    assert specs.ram_gb is None


def test_tb_storage_is_normalized_to_gb():
    specs = extract_specs("Notebook Dell Inspiron 15 com SSD 1TB e 16GB RAM")
    assert specs.storage_gb == 1024
    assert specs.ram_gb == 16


def test_pix_price_has_priority_over_higher_card_price():
    parsed = parse_message(
        "Impressora HP por R$ 1.939,00 no cartão ou R$ 1.842,05 no PIX"
    )
    assert parsed.price == Decimal("1842.05")
    assert parsed.old_price is None


def test_coupon_thresholds_are_not_product_prices():
    parsed = parse_message(
        "Cupom Amazon: R$150 OFF em compras a partir de R$1.499 - POUPE150"
    )
    assert parsed.price is None
    assert classify_message_kind(parsed) == COUPON


def test_coupon_code_can_appear_after_discount_description():
    text = "Cupom Amazon\nR$150 OFF em R$1499: POUPE150"
    assert extract_coupon(text) == "POUPE150"


def test_multi_product_list_is_marked_for_review():
    parsed = parse_message(
        "Placas-mãe em Oferta\n\n"
        "ASUS Prime B550M-A WiFi II - R$ 546\nhttps://loja/a\n"
        "Gigabyte B840M Eagle WiFi6 - R$ 599\nhttps://loja/b\n"
        "ASRock B650M-HDV/M.2 - R$ 659\nhttps://loja/c"
    )
    assert parsed.has_multiple_products is True
    assert classify_message_kind(parsed) == PRODUCT
    assert parsed.title_guess.startswith("ASUS Prime B550M")


def test_payment_options_are_not_marked_as_multiple_products():
    parsed = parse_message(
        "Perfume Essencial Oud 100ml\n"
        "POR: R$ 111,00\n"
        "Ou R$ 131,64 em até 12x"
    )
    assert parsed.has_multiple_products is False
    assert parsed.price == Decimal("111.00")
    assert parsed.old_price is None


def test_coupon_announcement_without_threshold_word_is_not_a_product():
    parsed = parse_message(
        "ALERTA de Cupom Amazon!\n\nR$ 60 OFF R$ 499 - Cupom: POUPEAGORA"
    )
    assert parsed.price is None
    assert parsed.coupon == "POUPEAGORA"
    assert classify_message_kind(parsed) == COUPON


def test_coupon_announcement_keeps_its_descriptive_first_line():
    parsed = parse_message(
        "Cupom Shopee R$20 acima de R$99\n\n🏷️ CUPOM\nhttps://loja/cupom"
    )
    assert parsed.title_guess == "Cupom Shopee R$20 acima de R$99"
