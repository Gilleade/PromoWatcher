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
    product_id: Optional[int] = None
    product_match_status: str = "UNMATCHED"
    product_match_confidence: Optional[float] = None
    listing_status: str = "ACTIVE"
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
    product_alert_id: Optional[int] = None
    id: Optional[int] = None


@dataclass
class Product:
    canonical_title: str
    variant_key: str
    category: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    variant_label: Optional[str] = None
    storage_gb: Optional[int] = None
    ram_gb: Optional[int] = None
    release_year: Optional[int] = None
    image_url: Optional[str] = None
    status: str = "ACTIVE"
    merged_into_product_id: Optional[int] = None
    lowest_price_ever: Optional[float] = None
    lowest_price_ever_at: Optional[str] = None
    last_price: Optional[float] = None
    last_price_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class ProductSpec:
    product_id: int
    spec_key: str
    spec_value: str
    confidence: Optional[float] = None
    source: str = "DETERMINISTIC"
    id: Optional[int] = None


@dataclass
class PriceHistoryPoint:
    product_id: int
    price: float
    promotion_id: Optional[int] = None
    old_price: Optional[float] = None
    coupon: Optional[str] = None
    store_domain: Optional[str] = None
    source_chat_title: Optional[str] = None
    is_bug_candidate: bool = False
    deviation_percent: Optional[float] = None
    id: Optional[int] = None


@dataclass
class Favorite:
    product_id: int
    id: Optional[int] = None


@dataclass
class ProductAlert:
    product_id: int
    enabled: bool = True
    max_price: Optional[float] = None
    send_to_telegram: bool = True
    id: Optional[int] = None


@dataclass
class StandaloneCoupon:
    raw_message_id: int
    code: Optional[str] = None
    discount_label: Optional[str] = None
    description: Optional[str] = None
    store_name: Optional[str] = None
    store_domain: Optional[str] = None
    url: Optional[str] = None
    dedupe_key: Optional[str] = None
    status: str = "ACTIVE"
    source_chat_title: Optional[str] = None
    repeat_count: int = 0
    id: Optional[int] = None
