from app.models import AlertDef
from app.parser.normalizer import normalize_text
from app.rules.alert_matcher import match_alert, match_alerts, sync_alerts_to_db


def _norm(text):
    return normalize_text(text)


def test_match_required_and_any_terms():
    alert = AlertDef(
        name="Notebook RTX 4050",
        required=["notebook", "rtx 4050"],
        any=["16gb", "lenovo loq"],
        exclude=["usado"],
        max_price=4500,
    )
    text = _norm("Notebook Lenovo LOQ RTX 4050 16GB por R$ 4.299,00")
    result = match_alert(text, alert)
    assert result.matched is True
    assert "notebook" in result.matched_required
    assert "rtx 4050" in result.matched_required
    assert result.matched_any


def test_missing_required_term_blocks_match():
    alert = AlertDef(name="Lava e seca LG", required=["lava e seca", "lg"])
    text = _norm("Lava e seca Brastemp 18kg")
    result = match_alert(text, alert)
    assert result.matched is False
    assert "não encontrou termos obrigatórios" in result.reason


def test_excluded_term_blocks_match():
    alert = AlertDef(name="Notebook", required=["notebook"], exclude=["usado"])
    text = _norm("Notebook usado em ótimo estado")
    result = match_alert(text, alert)
    assert result.matched is False
    assert "bloqueado" in result.reason


def test_bug_rule_matches_bug_keyword_parity_with_legacy():
    alert = AlertDef(name="Possível BUG geral", required=[], any=["bug"], exclude=[], bug_mode=True)
    text = _norm("Provável BUG: notebook por R$ 500,00")
    result = match_alert(text, alert)
    assert result.matched is True


def test_alert_without_terms_matches_anything():
    alert = AlertDef(name="Genérico", required=[], any=[], exclude=[])
    result = match_alert(_norm("qualquer texto"), alert)
    assert result.matched is True


def test_match_alerts_skips_disabled():
    alerts = [
        AlertDef(name="Ativo", required=[], any=["bug"], enabled=True),
        AlertDef(name="Inativo", required=[], any=["bug"], enabled=False),
    ]
    results = match_alerts(_norm("bug detectado"), alerts)
    assert len(results) == 1
    assert results[0].alert.name == "Ativo"


def test_tolerant_matching_ignores_accents_and_dashes():
    alert = AlertDef(name="Lava-louças", required=["lava loucas"])
    text = _norm("Comprei uma lava-louças nova")
    result = match_alert(text, alert)
    assert result.matched is True


def test_sync_alerts_to_db_assigns_ids_and_is_idempotent(db_conn):
    alerts = [AlertDef(name="Possível BUG geral", any=["bug"], bug_mode=True)]

    synced = sync_alerts_to_db(db_conn, alerts)
    assert synced[0].id is not None
    first_id = synced[0].id

    synced_again = sync_alerts_to_db(db_conn, alerts)
    assert synced_again[0].id == first_id

    count = db_conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    assert count == 1
