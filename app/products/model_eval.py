"""
Avalia candidatos de modelo Ollama para a tarefa de extração de specs de
produto (marca/modelo/armazenamento/RAM) a partir de texto de promoção real.

Rode com:  python -m app.products.model_eval

Modelos sugeridos para comparar (baixe o que quiser testar — é barato,
apaga depois se não servir):
    ollama pull nuextract:3.8b   # extrator dedicado, ~2.2GB
    ollama pull phi4-mini        # raciocínio forte, ~2.3GB em Q4
Já instalados neste projeto: qwen2.5:0.5b, qwen3:4b-instruct
"""
import sys
from dataclasses import dataclass
from typing import List, Optional

from app.config import get_config
from app.products.ollama_client import extract_specs_via_ollama, is_ollama_available, list_installed_models
from app.products.spec_extractor import extract_specs as extract_specs_deterministic

CANDIDATE_MODELS = [
    "qwen2.5:0.5b",
    "qwen3:4b-instruct",
    "nuextract:3.8b",
    "phi4-mini",
]


@dataclass
class TestCase:
    text: str
    expected_brand: Optional[str]
    expected_storage_gb: Optional[int]
    expected_ram_gb: Optional[int]


# Mistura de exemplos limpos e "sujos" (emoji, caps lock, gíria) — os mesmos
# tipos de caso usados para validar o extrator determinístico (Bloco 2).
TEST_CASES: List[TestCase] = [
    TestCase('Smartphone Motorola G56, 5G, 256 GB, 8 GB de RAM, Tela 6.7" Full HD+ | CUPOM + PIX',
             "motorola", 256, 8),
    TestCase("BUGOU!! Moto g56 5g 256gb so R$899 correee!!!", "motorola", 256, None),
    TestCase("CELULAR MOTOROLA G56 6/128GB PRETO - MENOR PRECO", "motorola", 128, 6),
    TestCase("Samsung Galaxy A55 8/128GB Preto por R$ 1.799,00", "samsung", 128, 8),
    TestCase("Notebook Dell Inspiron 15 8GB RAM 256GB SSD por R$ 2.999,00", "dell", 256, 8),
    TestCase("iPhone 15 128GB (Varios cores) a partir de R$3.999", "apple", 128, None),
    TestCase("PS5 Slim Digital + Gran Turismo 7 por R$3.629,99", "sony", None, None),
    TestCase("Fone JBL Tune 510BT Bluetooth por R$149,90", "jbl", None, None),
    TestCase("Xiaomi Redmi Note 13 6/128GB Azul, R$1.199 no Pix", "xiaomi", 128, 6),
    TestCase("Moto G56 5G 256GB direto da Motorola, correee", "motorola", 256, None),
    TestCase("Monitor Gamer AOC 24pol 165hz por R$899,90", "aoc", None, None),
    TestCase("Notebook Lenovo IdeaPad 3 Ryzen 5 8GB 512GB SSD R$2799", "lenovo", 512, 8),
    TestCase("MOTOROLA MOTO G55 5G 256GB 8GB RAM - CUPOM DISPONIVEL", "motorola", 256, 8),
    TestCase("Redragon Kumara teclado mecanico RGB por R$189,90", "redragon", None, None),
    TestCase("Galaxy S24 Ultra 512gb titanio preto - R$6999 a vista", "samsung", 512, None),
]


def _matches(expected, actual) -> bool:
    if expected is None:
        return True  # não cobramos precisão em campos que nem marquei como esperados
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().lower() == actual.strip().lower()
    return expected == actual


def evaluate_model(config, model: str, cases: List[TestCase]) -> dict:
    correct_brand = correct_storage = correct_ram = failures = 0
    total_latency = 0.0

    for case in cases:
        result = extract_specs_via_ollama(config, case.text, model=model)
        total_latency += result.latency_seconds
        if not result.ok:
            failures += 1
            continue
        correct_brand += _matches(case.expected_brand, result.brand)
        correct_storage += _matches(case.expected_storage_gb, result.storage_gb)
        correct_ram += _matches(case.expected_ram_gb, result.ram_gb)

    n = len(cases)
    return {
        "model": model,
        "brand_accuracy": correct_brand / n,
        "storage_accuracy": correct_storage / n,
        "ram_accuracy": correct_ram / n,
        "avg_latency_seconds": total_latency / n,
        "failures": failures,
    }


def evaluate_deterministic_baseline(cases: List[TestCase]) -> dict:
    correct_brand = correct_storage = correct_ram = 0
    for case in cases:
        specs = extract_specs_deterministic(case.text)
        correct_brand += _matches(case.expected_brand, specs.brand)
        correct_storage += _matches(case.expected_storage_gb, specs.storage_gb)
        correct_ram += _matches(case.expected_ram_gb, specs.ram_gb)
    n = len(cases)
    return {
        "model": "(baseline determinístico, sem IA)",
        "brand_accuracy": correct_brand / n,
        "storage_accuracy": correct_storage / n,
        "ram_accuracy": correct_ram / n,
        "avg_latency_seconds": 0.0,
        "failures": 0,
    }


def run_evaluation() -> List[dict]:
    config = get_config()
    results = [evaluate_deterministic_baseline(TEST_CASES)]

    if not is_ollama_available(config, force=True):
        print("Ollama não está acessível — pulando avaliação dos modelos de IA.")
        return results

    installed = list_installed_models(config)
    for model in CANDIDATE_MODELS:
        if model not in installed:
            print(f"[pulando] {model} não está instalado — rode: ollama pull {model}")
            continue
        print(f"Avaliando {model} em {len(TEST_CASES)} exemplos...")
        results.append(evaluate_model(config, model, TEST_CASES))

    return results


def print_results(results: List[dict]) -> None:
    header = f"{'Modelo':32} {'Marca':>7} {'Armaz.':>7} {'RAM':>7} {'Latência':>10} {'Falhas':>7}"
    print("\n" + header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['model']:32} {r['brand_accuracy']*100:6.0f}% {r['storage_accuracy']*100:6.0f}% "
            f"{r['ram_accuracy']*100:6.0f}% {r['avg_latency_seconds']:9.2f}s {r['failures']:7d}"
        )


def main():
    config = get_config()
    print(f"Verificando Ollama em {config.ollama_base_url}...")
    results = run_evaluation()
    print_results(results)


if __name__ == "__main__":
    main()
