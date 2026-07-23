from app.products.spec_extractor import build_variant_key, extract_specs


def test_extracts_brand_storage_ram_from_real_example():
    text = 'Smartphone Motorola G56, 5G, 256 GB, 8 GB de RAM, Tela 6.7" Full HD+ | CUPOM + PIX'
    specs = extract_specs(text)
    assert specs.brand == "motorola"
    assert specs.storage_gb == 256
    assert specs.ram_gb == 8
    assert specs.category == "smartphone"


def test_different_storage_yields_different_variant_key():
    text_256 = "Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90"
    text_128 = "Motorola Moto G56 5G 128GB 8GB RAM por R$ 899,90"

    specs_256 = extract_specs(text_256)
    specs_128 = extract_specs(text_128)

    key_256 = build_variant_key(specs_256.brand, specs_256.model, specs_256.storage_gb, specs_256.ram_gb)
    key_128 = build_variant_key(specs_128.brand, specs_128.model, specs_128.storage_gb, specs_128.ram_gb)

    assert specs_256.storage_gb == 256
    assert specs_128.storage_gb == 128
    assert key_256 != key_128


def test_same_product_from_different_wording_yields_same_variant_key():
    text_a = "Motorola Moto G56 5G 256GB 8GB RAM por R$ 1.093,90 no Magalu"
    text_b = "MOTOROLA MOTO G56 5G 256GB 8GB RAM - CUPOM DISPONIVEL"

    specs_a = extract_specs(text_a)
    specs_b = extract_specs(text_b)

    key_a = build_variant_key(specs_a.brand, specs_a.model, specs_a.storage_gb, specs_a.ram_gb)
    key_b = build_variant_key(specs_b.brand, specs_b.model, specs_b.storage_gb, specs_b.ram_gb)

    assert key_a == key_b


def test_combined_ram_storage_pattern():
    text = "Samsung Galaxy A55 8/128GB Preto por R$ 1.799,00"
    specs = extract_specs(text)
    assert specs.brand == "samsung"
    assert specs.ram_gb == 8
    assert specs.storage_gb == 128


def test_notebook_category_detection():
    text = "Notebook Dell Inspiron 15 8GB RAM 256GB SSD por R$ 2.999,00"
    specs = extract_specs(text)
    assert specs.brand == "dell"
    assert specs.category == "notebook"
    assert specs.storage_gb == 256
    assert specs.ram_gb == 8


def test_no_brand_or_specs_returns_low_confidence():
    specs = extract_specs("Promoção imperdível, corre que acaba rápido!")
    assert specs.brand is None
    assert specs.storage_gb is None
    assert specs.completeness_confidence == 0.0


def test_empty_text_does_not_raise():
    specs = extract_specs("")
    assert specs.brand is None
    assert specs.completeness_confidence == 0.0


def test_release_year_extraction():
    specs = extract_specs("iPhone 15 Pro Max lançado em 2023, 256GB")
    assert specs.release_year == 2023


def test_build_variant_key_uses_placeholder_for_missing_fields():
    key = build_variant_key(None, None, None, None)
    assert key == "?|?|?|?"


def test_variant_label_combines_storage_and_ram():
    specs = extract_specs("Motorola Moto G56 256GB 8GB RAM")
    assert specs.variant_label == "256GB 8GB RAM"


def test_brand_recognized_without_literal_brand_name():
    # "Moto" sem "Motorola" escrito é o jeito mais comum de postar no Telegram
    specs = extract_specs("BUGOU!! Moto g56 5g 256gb so R$899 correee!!!")
    assert specs.brand == "motorola"
    assert specs.storage_gb == 256


def test_model_extraction_stops_at_connector_word_without_price_or_gb():
    specs = extract_specs("Fone JBL Tune 510BT Bluetooth por R$149,90")
    assert specs.brand == "jbl"
    assert "por" not in (specs.model or "").split()


def test_repeated_brand_mention_uses_earliest_occurrence():
    specs = extract_specs("Moto G56 5G 256GB direto da Motorola")
    assert specs.brand == "motorola"
    assert specs.model == "g56 5g"


def test_console_brand_alias_ps5():
    specs = extract_specs("PS5 Slim Digital + Gran Turismo 7 por R$3.629,99")
    assert specs.brand == "sony"
    assert specs.category == "console"


def test_mechanical_keyboard_switch_does_not_false_positive_as_nintendo():
    # bug real: "Cherry MX Red Switch Hot-Swappable" fazia o extrator marcar
    # a marca como "nintendo" (gatilho "switch" sozinho, sem "nintendo" no
    # texto) — um teclado gamer virava um "produto Nintendo" no catálogo.
    text = (
        "Teclado Mecânico Gamer AGON AGK600 Cherry MX Red Switch "
        "Hot-Swappable US RGB 360° com design 60% ultracompacto"
    )
    specs = extract_specs(text)
    assert specs.brand is None
    assert specs.category == "teclado"
