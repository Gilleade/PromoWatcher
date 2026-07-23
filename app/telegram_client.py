from telethon import TelegramClient

from app.config import Config


def create_client(config: Config) -> TelegramClient:
    return TelegramClient(config.session_name, config.telegram_api_id, config.telegram_api_hash)
