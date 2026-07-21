from unittest.mock import Mock, patch

import requests

from app.services.telegram_bot_notifier import send_promo_bot_message


def test_does_not_send_without_complete_configuration():
    sent, error = send_promo_bot_message(token="", chat_id="123", text="promo")

    assert sent is False
    assert error == "CONFIG_INCOMPLETA"


@patch("app.services.telegram_bot_notifier.requests.post")
def test_sends_message_to_configured_bot(mock_post):
    mock_post.return_value = Mock(ok=True, status_code=200)

    sent, error = send_promo_bot_message(token="token-de-teste", chat_id="123", text="promo")

    assert sent is True
    assert error is None
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["json"] == {
        "chat_id": "123",
        "text": "promo",
        "disable_web_page_preview": True,
    }


@patch("app.services.telegram_bot_notifier.requests.post")
def test_returns_safe_error_on_network_failure(mock_post):
    mock_post.side_effect = requests.Timeout("https://api.telegram.org/botsegredo/sendMessage")

    sent, error = send_promo_bot_message(token="token-de-teste", chat_id="123", text="promo")

    assert sent is False
    assert error == "Timeout"
