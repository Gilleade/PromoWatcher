from app.products.hybrid_classifier import classify_hybrid
from app.products.ollama_client import OllamaExtractionResult


def test_agreement_confirms_category_and_only_evidenced_fields():
    result = classify_hybrid(
        deterministic_specs={"category": "placa_video", "brand": "amd", "model": None},
        ai_extraction=OllamaExtractionResult(
            ok=True, category="graphics_card", brand="inventada",
            model="RX 7600", storage_gb=1799,
        ),
        raw_text="Placa de Vídeo AMD Radeon RX 7600 8GB GDDR6 por R$ 1.799",
    )
    assert result.status == "CONFIRMED"
    assert result.selected_category == "graphics_card"
    assert result.validated_ai_fields == {"model": "RX 7600"}
    assert result.rejected_ai_fields["storage_gb"] == "sem evidência no texto da promoção"


def test_deterministic_category_wins_over_ai_conflict():
    result = classify_hybrid(
        deterministic_specs={"category": "notebook"},
        ai_extraction=OllamaExtractionResult(ok=True, category="smartphone"),
        raw_text="Notebook Lenovo Ideapad 1TB SSD",
    )
    assert result.status == "CONFLICT"
    assert result.selected_category == "notebook"
    assert result.rejected_ai_fields["category"] == "conflita com a regra determinística"


def test_ai_only_category_remains_candidate_in_shadow():
    result = classify_hybrid(
        deterministic_specs={"category": None},
        ai_extraction=OllamaExtractionResult(ok=True, category="air_fryer"),
        raw_text="Fritadeira sem óleo 5 litros",
    )
    assert result.status == "AI_CANDIDATE"
    assert result.ai_category == "air_fryer"
    assert result.selected_category is None


def test_unknown_ai_category_is_rejected():
    result = classify_hybrid(
        deterministic_specs={"category": None},
        ai_extraction=OllamaExtractionResult(ok=True, category="produto premium"),
        raw_text="Produto premium em oferta",
    )
    assert result.status == "UNRESOLVED"
    assert result.rejected_ai_fields["category"] == "categoria fora do catálogo oficial"


def test_price_cannot_become_ram_or_storage():
    result = classify_hybrid(
        deterministic_specs={"category": "smartphone", "ram_gb": None, "storage_gb": None},
        ai_extraction=OllamaExtractionResult(
            ok=True, category="smartphone", ram_gb=1329, storage_gb=1329,
        ),
        raw_text="Smartphone Nike edição especial por R$ 1.329",
    )
    assert result.validated_ai_fields == {}
    assert set(result.rejected_ai_fields) == {"ram_gb", "storage_gb"}


def test_explicit_ram_and_storage_are_accepted():
    result = classify_hybrid(
        deterministic_specs={"category": "notebook", "ram_gb": None, "storage_gb": None},
        ai_extraction=OllamaExtractionResult(
            ok=True, category="notebook", ram_gb=16, storage_gb=512,
        ),
        raw_text="Notebook Dell com 16GB de RAM e SSD de 512GB",
    )
    assert result.validated_ai_fields == {"storage_gb": 512, "ram_gb": 16}
