import pytest

from app.products.taxonomy_catalog import (
    CATALOG_VERSION,
    LEGACY_CATEGORY_ALIASES,
    canonical_category,
    get_category_profile,
    load_category_catalog,
)


def test_official_catalog_has_all_reviewed_profiles():
    catalog = load_category_catalog()
    assert CATALOG_VERSION == "1.0.0"
    assert len(catalog) == 60
    assert {"smartphone", "notebook", "console", "air_fryer", "dishwasher"} <= set(catalog)


def test_profiles_define_identity_and_controlled_metadata():
    smartphone = get_category_profile("smartphone")
    assert smartphone is not None
    assert smartphone.family == "mobile"
    assert smartphone.identity_fields == ("brand", "model")
    assert "storage_gb" in smartphone.variant_fields
    assert smartphone.priority == "HIGH"
    assert smartphone.status == "PROPOSED"


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("placa_mae", "motherboard"),
        ("placa_video", "graphics_card"),
        ("processador", "processor"),
        ("fone", "audio"),
        ("teclado", "computer_peripheral"),
    ],
)
def test_legacy_categories_have_explicit_compatibility_aliases(legacy, canonical):
    assert LEGACY_CATEGORY_ALIASES[legacy] == canonical
    assert canonical_category(legacy) == canonical
    assert get_category_profile(legacy) == get_category_profile(canonical)


def test_unknown_category_is_not_forced_into_other():
    assert canonical_category("categoria_inventada") is None
    assert get_category_profile("categoria_inventada") is None


def test_loaded_catalog_is_immutable():
    with pytest.raises(TypeError):
        load_category_catalog()["new"] = get_category_profile("smartphone")
