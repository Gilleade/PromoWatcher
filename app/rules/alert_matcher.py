import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import List

from app.database import upsert_alert
from app.models import AlertDef
from app.parser.normalizer import normalize_text


def load_alerts(path: str) -> List[AlertDef]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    alerts = []
    for item in raw:
        alerts.append(AlertDef(
            name=item["name"],
            enabled=item.get("enabled", True),
            alert_type=item.get("alert_type", "PRODUCT_RULE"),
            required=item.get("required", []),
            any=item.get("any", []),
            exclude=item.get("exclude", []),
            max_price=item.get("max_price"),
            min_discount_percent=item.get("min_discount_percent"),
            bug_mode=item.get("bug_mode", False),
            min_score=item.get("min_score", 0),
            send_to_telegram=item.get("send_to_telegram", True),
        ))
    return alerts


def save_alerts(path: str, alerts: List[AlertDef]) -> None:
    """Serializa alerts.json de volta para o disco. Escrita atômica
    (arquivo temporário + os.replace) para não corromper o arquivo se o
    processo for interrompido no meio da escrita."""
    raw = [
        {
            "name": a.name,
            "enabled": a.enabled,
            "alert_type": a.alert_type,
            "required": a.required,
            "any": a.any,
            "exclude": a.exclude,
            "max_price": a.max_price,
            "min_discount_percent": a.min_discount_percent,
            "bug_mode": a.bug_mode,
            "min_score": a.min_score,
            "send_to_telegram": a.send_to_telegram,
        }
        for a in alerts
    ]
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_path, path)


def sync_alerts_to_db(conn: sqlite3.Connection, alerts: List[AlertDef]) -> List[AlertDef]:
    """Espelha alerts.json (fonte da verdade) na tabela `alerts`, preenchendo
    o id de cada AlertDef para que promotions.matched_alert_id seja válido."""
    for alert in alerts:
        alert.id = upsert_alert(
            conn,
            name=alert.name,
            enabled=alert.enabled,
            alert_type=alert.alert_type,
            required_terms=json.dumps(alert.required),
            optional_terms=json.dumps(alert.any),
            excluded_terms=json.dumps(alert.exclude),
            min_price=None,
            max_price=alert.max_price,
            min_discount_percent=alert.min_discount_percent,
            bug_mode=alert.bug_mode,
            min_score=alert.min_score,
            send_to_telegram=alert.send_to_telegram,
        )
    return alerts


def _term_regex(term: str) -> re.Pattern:
    normalized = normalize_text(term)
    parts = normalized.split()
    regex_str = r"[\s\-]*".join(re.escape(p) for p in parts)
    if regex_str.endswith("a"):
        regex_str += "s?"
    return re.compile(regex_str)


def _term_matches(term: str, normalized_text: str) -> bool:
    return bool(_term_regex(term).search(normalized_text))


@dataclass
class MatchResult:
    alert: AlertDef
    matched: bool
    matched_required: List[str] = field(default_factory=list)
    matched_any: List[str] = field(default_factory=list)
    matched_excluded: List[str] = field(default_factory=list)
    reason: str = ""


def match_alert(normalized_text: str, alert: AlertDef) -> MatchResult:
    matched_excluded = [t for t in alert.exclude if _term_matches(t, normalized_text)]
    if matched_excluded:
        return MatchResult(
            alert=alert, matched=False, matched_excluded=matched_excluded,
            reason=f"Ignorado porque contém termo bloqueado: {', '.join(matched_excluded)}.",
        )

    matched_required = [t for t in alert.required if _term_matches(t, normalized_text)]
    missing_required = [t for t in alert.required if t not in matched_required]
    if missing_required:
        return MatchResult(
            alert=alert, matched=False, matched_required=matched_required,
            reason=f"Ignorado porque não encontrou termos obrigatórios: {', '.join(missing_required)}.",
        )

    matched_any = [t for t in alert.any if _term_matches(t, normalized_text)]
    if alert.any and not matched_any:
        return MatchResult(
            alert=alert, matched=False, matched_required=matched_required,
            reason="Ignorado porque nenhum termo opcional foi encontrado.",
        )

    found_terms = matched_required + matched_any
    reason = (
        f"Aprovado porque encontrou: {', '.join(found_terms)}."
        if found_terms else "Aprovado (regra sem termos obrigatórios/opcionais)."
    )
    return MatchResult(
        alert=alert, matched=True, matched_required=matched_required,
        matched_any=matched_any, reason=reason,
    )


def match_alerts(normalized_text: str, alerts: List[AlertDef]) -> List[MatchResult]:
    return [match_alert(normalized_text, a) for a in alerts if a.enabled]
