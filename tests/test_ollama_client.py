import json
from unittest.mock import Mock, patch

import requests

from app.config import Config
from app.products.ollama_client import (
    disambiguate_product,
    extract_specs_via_ollama,
    is_ollama_available,
    list_installed_models,
)


def _config(**overrides):
    cfg = Config()
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


def _fake_generate_response(payload: dict):
    return Mock(status_code=200, json=lambda: {"response": json.dumps(payload)},
                raise_for_status=lambda: None)


def test_is_ollama_available_true_when_reachable():
    with patch("app.products.ollama_client.requests.get", return_value=Mock(status_code=200)):
        assert is_ollama_available(_config(), force=True) is True


def test_is_ollama_available_false_when_unreachable():
    with patch("app.products.ollama_client.requests.get", side_effect=requests.exceptions.ConnectionError):
        assert is_ollama_available(_config(), force=True) is False


def test_list_installed_models_returns_names():
    fake = Mock(status_code=200, raise_for_status=lambda: None,
                json=lambda: {"models": [{"name": "qwen2.5:0.5b"}, {"name": "qwen3:4b-instruct"}]})
    with patch("app.products.ollama_client.requests.get", return_value=fake):
        assert list_installed_models(_config()) == ["qwen2.5:0.5b", "qwen3:4b-instruct"]


def test_list_installed_models_empty_on_error():
    with patch("app.products.ollama_client.requests.get", side_effect=requests.exceptions.Timeout):
        assert list_installed_models(_config()) == []


def test_extract_specs_via_ollama_success():
    fake_response = _fake_generate_response({
        "brand": "motorola", "model": "moto g56 5g", "storage_gb": 256,
        "ram_gb": 8, "category": "smartphone", "release_year": None,
    })
    with patch("app.products.ollama_client.requests.post", return_value=fake_response):
        result = extract_specs_via_ollama(_config(), "Moto G56 5G 256GB 8GB RAM por R$ 1093,90")

    assert result.ok is True
    assert result.brand == "motorola"
    assert result.storage_gb == 256


def test_extract_specs_via_ollama_never_raises_on_timeout():
    with patch("app.products.ollama_client.requests.post", side_effect=requests.exceptions.Timeout):
        result = extract_specs_via_ollama(_config(), "qualquer texto")

    assert result.ok is False
    assert result.error is not None


def test_extract_specs_via_ollama_never_raises_on_invalid_json():
    bad_response = Mock(status_code=200, raise_for_status=lambda: None,
                         json=lambda: {"response": "isso não é json"})
    with patch("app.products.ollama_client.requests.post", return_value=bad_response):
        result = extract_specs_via_ollama(_config(), "qualquer texto")

    assert result.ok is False


def test_disambiguate_product_returns_match_decision():
    fake_response = _fake_generate_response({
        "decision": "MATCH", "product_id": 42, "confidence": 0.9,
        "canonical_title": "Motorola Moto G56 5G 256GB", "brand": "motorola",
        "model": "moto g56 5g", "storage_gb": 256, "ram_gb": 8,
        "reason": "Mesmo aparelho, so mudou o texto do anuncio.",
    })
    with patch("app.products.ollama_client.requests.post", return_value=fake_response):
        result = disambiguate_product(
            _config(), extracted={"brand": "motorola"}, raw_text="Moto G56 5G 256GB",
            candidates=[{"id": 42, "canonical_title": "Motorola Moto G56 5G 256GB",
                         "brand": "motorola", "model": "moto g56 5g", "storage_gb": 256, "ram_gb": 8}],
        )

    assert result.decision == "MATCH"
    assert result.product_id == 42


def test_disambiguate_product_falls_back_to_unsure_when_ollama_down():
    with patch("app.products.ollama_client.requests.post", side_effect=requests.exceptions.ConnectionError):
        result = disambiguate_product(
            _config(), extracted={"brand": "motorola"}, raw_text="Moto G56 5G 256GB", candidates=[],
        )

    assert result.decision == "UNSURE"


def test_disambiguate_product_disabled_returns_unsure_without_network_call():
    with patch("app.products.ollama_client.requests.post") as mock_post:
        result = disambiguate_product(
            _config(ollama_enabled=False), extracted={}, raw_text="x", candidates=[],
        )
    assert result.decision == "UNSURE"
    mock_post.assert_not_called()


def test_disambiguate_product_rejects_invalid_decision_value():
    fake_response = _fake_generate_response({
        "decision": "TALVEZ", "confidence": 0.5, "reason": "modelo respondeu algo fora do enum",
    })
    with patch("app.products.ollama_client.requests.post", return_value=fake_response):
        result = disambiguate_product(_config(), extracted={}, raw_text="x", candidates=[])

    assert result.decision == "UNSURE"


def test_disambiguate_product_normalizes_invalid_confidence():
    fake_response = _fake_generate_response({
        "decision": "NEW", "confidence": "alta", "reason": "valor inválido",
    })
    with patch("app.products.ollama_client.requests.post", return_value=fake_response):
        result = disambiguate_product(_config(), extracted={}, raw_text="x", candidates=[])

    assert result.confidence == 0.0
