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

    # Segundo destino opcional: bot dedicado para alertas de promoções.
    promo_bot_enabled: bool = _bool("PROMO_BOT_ENABLED", "false")
    promo_bot_token: str = os.getenv("PROMO_BOT_TOKEN", "").strip()
    promo_bot_chat_id: str = os.getenv("PROMO_BOT_CHAT_ID", "").strip()

    db_path: str = os.getenv("DB_PATH", os.path.join("data", "promowatcher.sqlite3"))
    alerts_file: str = os.getenv("ALERTS_FILE", "alerts.json")

    images_dir: str = os.getenv("IMAGES_DIR", os.path.join("data", "images"))
    media_download_timeout: float = float(os.getenv("MEDIA_DOWNLOAD_TIMEOUT", "15"))

    case_insensitive: bool = _bool("CASE_INSENSITIVE", "true")
    accent_insensitive: bool = _bool("ACCENT_INSENSITIVE", "true")
    normalize_spaces_dashes: bool = _bool("NORMALIZE_SPACES_DASHES", "true")

    link_resolve_timeout: float = float(os.getenv("LINK_RESOLVE_TIMEOUT", "5"))

    ollama_enabled: bool = _bool("OLLAMA_ENABLED", "true")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_extract_model: str = os.getenv("OLLAMA_EXTRACT_MODEL", "qwen2.5:0.5b")
    ollama_match_model: str = os.getenv("OLLAMA_MATCH_MODEL", "qwen3:4b-instruct")
    ollama_timeout: float = float(os.getenv("OLLAMA_TIMEOUT", "20"))
    ollama_keep_alive: str = os.getenv("OLLAMA_KEEP_ALIVE", "5m")
    # Proteção temporária: a IA analisa e registra a decisão, mas não pode
    # criar produtos nem associar promoções enquanto a nova taxonomia é validada.
    ollama_shadow_mode: bool = _bool("OLLAMA_SHADOW_MODE", "true")


def get_config() -> Config:
    return Config()
