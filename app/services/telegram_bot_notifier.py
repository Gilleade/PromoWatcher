"""Entrega opcional de alertas por um bot dedicado do Telegram.

O módulo não conhece regras de promoção nem o watcher: recebe apenas o texto
já aprovado pelo pipeline e o envia pela Bot API. Erros são reduzidos a códigos
seguros para nunca registrar o token nos logs ou no banco.
"""

from typing import Optional, Tuple

import requests


BOT_API_TIMEOUT_SECONDS = 10


def send_promo_bot_message(*, token: str, chat_id: str, text: str) -> Tuple[bool, Optional[str]]:
    """Envia ``text`` ao chat configurado e devolve um resultado seguro para log."""
    if not token or not chat_id:
        return False, "CONFIG_INCOMPLETA"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    try:
        response = requests.post(url, json=payload, timeout=BOT_API_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        return False, type(exc).__name__

    if not response.ok:
        return False, f"HTTP_{response.status_code}"
    return True, None
