import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() == "true"


@dataclass
class Config:
    telegram_api_id: int = int(os.getenv("TELEGRAM_API_ID", "0"))
    telegram_api_hash: str = os.getenv("TELEGRAM_API_HASH", "")
    telegram_chats: list = field(default_factory=lambda: [
        c.strip() for c in os.getenv("TELEGRAM_CHATS", "").split(",") if c.strip()
    ])
    notify_chat: str = os.getenv("NOTIFY_CHAT", "").strip() or "me"
    session_name: str = os.getenv("SESSION_NAME", "tg_promos_session")

    db_path: str = os.getenv("DB_PATH", os.path.join("data", "promowatcher.sqlite3"))
    alerts_file: str = os.getenv("ALERTS_FILE", "alerts.json")

    case_insensitive: bool = _bool("CASE_INSENSITIVE", "true")
    accent_insensitive: bool = _bool("ACCENT_INSENSITIVE", "true")
    normalize_spaces_dashes: bool = _bool("NORMALIZE_SPACES_DASHES", "true")

    link_resolve_timeout: float = float(os.getenv("LINK_RESOLVE_TIMEOUT", "5"))


def get_config() -> Config:
    return Config()
