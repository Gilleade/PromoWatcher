from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RawMessage:
    telegram_message_id: int
    chat_id: int
    chat_title: str
    sender_id: Optional[int]
    message_text: str
    message_date: datetime
    has_media: bool = False
    media_type: Optional[str] = None
    raw_json: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Promotion:
    raw_message_id: int
    title_guess: Optional[str] = None
    price: Optional[float] = None
    old_price: Optional[float] = None
    discount_percent: Optional[float] = None
    coupon: Optional[str] = None
    source_chat_title: Optional[str] = None
    original_links: Optional[str] = None
    selected_original_url: Optional[str] = None
    resolved_url: Optional[str] = None
    clean_url: Optional[str] = None
    link_status: Optional[str] = None
    store_domain: Optional[str] = None
    dedupe_key: Optional[str] = None
    status: Optional[str] = None
    score: Optional[int] = None
    matched_alert_id: Optional[int] = None
    repeat_count: int = 0
    id: Optional[int] = None


@dataclass
class AlertDef:
    name: str
    enabled: bool = True
    alert_type: str = "PRODUCT_RULE"
    required: list = field(default_factory=list)
    any: list = field(default_factory=list)
    exclude: list = field(default_factory=list)
    max_price: Optional[float] = None
    min_discount_percent: Optional[float] = None
    bug_mode: bool = False
    min_score: int = 0
    send_to_telegram: bool = True
    id: Optional[int] = None


@dataclass
class PromotionOccurrence:
    promotion_id: int
    raw_message_id: int
    chat_title: str
    message_date: datetime
    original_url: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Notification:
    promotion_id: int
    alert_id: Optional[int]
    channel: str
    message_sent: str
    status: str = "SENT"
    error_message: Optional[str] = None
    id: Optional[int] = None
