from unittest.mock import Mock, patch

from app.models import AlertDef
from app.services.message_processor import process


def _bug_alert():
    return AlertDef(name="Possível BUG geral", required=[], any=["bug"], exclude=[],
                     bug_mode=True, min_score=0, send_to_telegram=True)


def _notebook_alert():
    return AlertDef(name="Notebook RTX 4050", required=["notebook", "rtx 4050"],
                     any=["16gb"], exclude=["usado"], max_price=4500, min_score=0)


def test_process_new_message_approved_and_notifies(db_conn):
    fake_response = Mock(status_code=200, url="https://loja.com/produto?tag=xyz")
    with patch("app.parser.link_resolver.requests.head", return_value=fake_response):
        result = process(
            db_conn,
            telegram_message_id=1,
            chat_id=100,
            chat_title="Grupo A",
            sender_id=None,
            message_text="Provável BUG: Notebook por R$ 500,00 https://loja.com/produto",
            message_date="2026-07-01T10:00:00",
            alerts=[_bug_alert()],
        )
    assert result.status == "NEW_APPROVED"
    assert result.notify is True
    assert result.promotion_id is not None
    assert result.matched_alert.name == "Possível BUG geral"


def test_process_no_match_is_ignored(db_conn):
    with patch("app.parser.link_resolver.requests.head", side_effect=ConnectionError):
        result = process(
            db_conn,
            telegram_message_id=2,
            chat_id=100,
            chat_title="Grupo A",
            sender_id=None,
            message_text="Sem nenhum termo relevante aqui",
            message_date="2026-07-01T10:00:00",
            alerts=[_notebook_alert()],
        )
    assert result.status == "NEW_IGNORED"
    assert result.notify is False


def test_process_duplicate_message_registers_occurrence(db_conn):
    fake_response = Mock(status_code=200, url="https://loja.com/produto-x")
    with patch("app.parser.link_resolver.requests.head", return_value=fake_response):
        first = process(
            db_conn,
            telegram_message_id=10,
            chat_id=100,
            chat_title="Grupo A",
            sender_id=None,
            message_text="BUG: Notebook por R$ 500,00 https://loja.com/produto-x",
            message_date="2026-07-01T10:00:00",
            alerts=[_bug_alert()],
        )
        second = process(
            db_conn,
            telegram_message_id=11,
            chat_id=200,
            chat_title="Grupo B",
            sender_id=None,
            message_text="BUG: Notebook por R$ 500,00 https://loja.com/produto-x",
            message_date="2026-07-01T10:05:00",
            alerts=[_bug_alert()],
        )

    assert first.status == "NEW_APPROVED"
    assert second.status == "DUPLICATE"
    assert second.promotion_id == first.promotion_id

    row = db_conn.execute(
        "SELECT repeat_count FROM promotions WHERE id = ?", (first.promotion_id,)
    ).fetchone()
    assert row["repeat_count"] == 1


def test_process_excluded_term_is_ignored_with_reason(db_conn):
    with patch("app.parser.link_resolver.requests.head", side_effect=ConnectionError):
        result = process(
            db_conn,
            telegram_message_id=20,
            chat_id=100,
            chat_title="Grupo A",
            sender_id=None,
            message_text="Notebook RTX 4050 usado, 16GB por R$ 3.000,00",
            message_date="2026-07-01T10:00:00",
            alerts=[_notebook_alert()],
        )
    assert result.status == "NEW_IGNORED"
    assert "bloqueado" in result.reason
