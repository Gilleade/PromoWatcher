import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from app.config import Config

_AVAILABILITY_CACHE_TTL_SECONDS = 5.0
_availability_cache = {"checked_at": 0.0, "available": False}


@dataclass
class OllamaExtractionResult:
    ok: bool = False
    brand: Optional[str] = None
    model: Optional[str] = None
    storage_gb: Optional[int] = None
    ram_gb: Optional[int] = None
    category: Optional[str] = None
    release_year: Optional[int] = None
    error: Optional[str] = None
    latency_seconds: float = 0.0


@dataclass
class OllamaMatchResult:
    decision: str = "UNSURE"  # MATCH | NEW | UNSURE
    product_id: Optional[int] = None
    confidence: float = 0.0
    canonical_title: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    storage_gb: Optional[int] = None
    ram_gb: Optional[int] = None
    reason: str = ""
    latency_seconds: float = 0.0


_EXTRACTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "brand": {"type": ["string", "null"]},
        "model": {"type": ["string", "null"]},
        "storage_gb": {"type": ["integer", "null"]},
        "ram_gb": {"type": ["integer", "null"]},
        "category": {"type": ["string", "null"]},
        "release_year": {"type": ["integer", "null"]},
    },
    "required": ["brand", "model", "storage_gb", "ram_gb"],
}

_MATCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["MATCH", "NEW", "UNSURE"]},
        "product_id": {"type": ["integer", "null"]},
        "confidence": {"type": "number"},
        "canonical_title": {"type": ["string", "null"]},
        "brand": {"type": ["string", "null"]},
        "model": {"type": ["string", "null"]},
        "storage_gb": {"type": ["integer", "null"]},
        "ram_gb": {"type": ["integer", "null"]},
        "reason": {"type": "string"},
    },
    "required": ["decision", "confidence", "reason"],
}


def is_ollama_available(config: Config, *, timeout: float = 2.0, force: bool = False) -> bool:
    """Checagem barata e cacheada — não martela o serviço a cada mensagem
    quando ele está fora do ar."""
    now = time.monotonic()
    if not force and (now - _availability_cache["checked_at"]) < _AVAILABILITY_CACHE_TTL_SECONDS:
        return _availability_cache["available"]

    available = False
    try:
        response = requests.get(f"{config.ollama_base_url}/api/tags", timeout=timeout)
        available = response.status_code == 200
    except requests.exceptions.RequestException:
        available = False

    _availability_cache["checked_at"] = now
    _availability_cache["available"] = available
    return available


def list_installed_models(config: Config, *, timeout: float = 2.0) -> List[str]:
    try:
        response = requests.get(f"{config.ollama_base_url}/api/tags", timeout=timeout)
        response.raise_for_status()
        return [m["name"] for m in response.json().get("models", [])]
    except requests.exceptions.RequestException:
        return []


def _call_ollama_structured(config: Config, *, model: str, prompt: str,
                             schema: Dict[str, Any], timeout: Optional[float] = None) -> Optional[dict]:
    """Chamada de baixo nível com saída restrita a um JSON Schema (recurso
    nativo do Ollama). Nunca lança exceção — qualquer falha (serviço fora do
    ar, timeout, resposta fora do schema) retorna None, e quem chamou decide
    o fallback (normalmente UNSURE / revisão humana)."""
    try:
        response = requests.post(
            f"{config.ollama_base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "format": schema,
                "stream": False,
                "keep_alive": config.ollama_keep_alive,
                "options": {"temperature": 0},
            },
            timeout=timeout or config.ollama_timeout,
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        return json.loads(raw)
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError, ValueError):
        return None


def extract_specs_via_ollama(config: Config, raw_text: str, *,
                              model: Optional[str] = None) -> OllamaExtractionResult:
    prompt = (
        "Extraia as especificações do produto anunciado na mensagem de promoção "
        "abaixo (grupo de Telegram brasileiro, texto pode ter emojis/gírias). "
        "Responda apenas com os campos pedidos; use null quando não tiver certeza.\n\n"
        f"Mensagem: {raw_text}"
    )
    start = time.monotonic()
    data = _call_ollama_structured(
        config, model=model or config.ollama_extract_model, prompt=prompt, schema=_EXTRACTION_SCHEMA,
    )
    elapsed = time.monotonic() - start

    if data is None:
        return OllamaExtractionResult(ok=False, error="sem resposta válida do Ollama", latency_seconds=elapsed)

    return OllamaExtractionResult(
        ok=True,
        brand=data.get("brand"),
        model=data.get("model"),
        storage_gb=data.get("storage_gb"),
        ram_gb=data.get("ram_gb"),
        category=data.get("category"),
        release_year=data.get("release_year"),
        latency_seconds=elapsed,
    )


def _format_candidates(candidates: List[dict]) -> str:
    if not candidates:
        return "(nenhum candidato encontrado)"
    lines = []
    for c in candidates:
        lines.append(
            f"- id={c.get('id')} titulo=\"{c.get('canonical_title')}\" marca={c.get('brand')} "
            f"modelo={c.get('model')} armazenamento={c.get('storage_gb')}GB ram={c.get('ram_gb')}GB"
        )
    return "\n".join(lines)


def disambiguate_product(config: Config, *, extracted: dict, raw_text: str,
                          candidates: List[dict], model: Optional[str] = None) -> OllamaMatchResult:
    """Usada quando o matching determinístico ficou em zona cinzenta. Nunca
    lança exceção — falha vira UNSURE, que cai para revisão humana."""
    if not config.ollama_enabled:
        return OllamaMatchResult(decision="UNSURE", reason="Ollama desabilitado por configuração.")

    prompt = (
        "Você ajuda a organizar um catálogo de produtos de promoções do Telegram. "
        "Decida se a mensagem abaixo é o MESMO produto de algum dos candidatos já "
        "cadastrados, ou se é um produto NOVO. Marca e armazenamento diferentes "
        "NUNCA são o mesmo produto. Na dúvida, responda UNSURE.\n\n"
        f"Mensagem: {raw_text}\n\n"
        f"Specs extraídas: {json.dumps(extracted, ensure_ascii=False)}\n\n"
        f"Candidatos já cadastrados:\n{_format_candidates(candidates)}"
    )
    start = time.monotonic()
    data = _call_ollama_structured(
        config, model=model or config.ollama_match_model, prompt=prompt, schema=_MATCH_SCHEMA,
    )
    elapsed = time.monotonic() - start

    if data is None:
        return OllamaMatchResult(decision="UNSURE", reason="sem resposta válida do Ollama", latency_seconds=elapsed)

    decision = data.get("decision")
    if decision not in ("MATCH", "NEW", "UNSURE"):
        decision = "UNSURE"

    return OllamaMatchResult(
        decision=decision,
        product_id=data.get("product_id"),
        confidence=float(data.get("confidence") or 0.0),
        canonical_title=data.get("canonical_title"),
        brand=data.get("brand"),
        model=data.get("model"),
        storage_gb=data.get("storage_gb"),
        ram_gb=data.get("ram_gb"),
        reason=data.get("reason", ""),
        latency_seconds=elapsed,
    )
