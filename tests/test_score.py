from decimal import Decimal

from app.models import AlertDef
from app.rules.alert_matcher import MatchResult
from app.rules.score import compute_score


def test_score_all_required_and_price_below_max():
    alert = AlertDef(name="Notebook", required=["notebook", "rtx 4050"], max_price=4500)
    match_result = MatchResult(alert=alert, matched=True,
                                matched_required=["notebook", "rtx 4050"])
    result = compute_score(normalized_text="notebook rtx 4050 por 4299",
                            price=Decimal("4299"), match_result=match_result)
    assert result.score == 60  # +40 obrigatórios + 20 preço abaixo do máximo


def test_score_bug_term_adds_points():
    alert = AlertDef(name="Bug", any=["bug"])
    match_result = MatchResult(alert=alert, matched=True, matched_any=["bug"])
    result = compute_score(normalized_text="provavel bug notebook",
                            price=None, match_result=match_result)
    assert result.score == 15 + 15  # +15 opcional + 15 termo de bug


def test_score_known_store_domain_adds_points():
    alert = AlertDef(name="Generico")
    match_result = MatchResult(alert=alert, matched=True)
    result = compute_score(normalized_text="produto qualquer", price=None,
                            match_result=match_result, store_domain="www.amazon.com.br")
    assert result.score == 10


def test_score_excluded_term_subtracts_points():
    alert = AlertDef(name="Notebook", required=["notebook"], exclude=["usado"])
    match_result = MatchResult(alert=alert, matched=False, matched_excluded=["usado"])
    result = compute_score(normalized_text="notebook usado", price=None,
                            match_result=match_result)
    assert result.score == -50


def test_score_missing_price_when_required_subtracts_points():
    alert = AlertDef(name="Notebook", required=["notebook"], max_price=4500)
    match_result = MatchResult(alert=alert, matched=True, matched_required=["notebook"])
    result = compute_score(normalized_text="notebook sem preco visivel", price=None,
                            match_result=match_result)
    assert result.score == 40 - 30
