from typing import List, Optional

from pydantic import BaseModel


class ProductCard(BaseModel):
    id: int
    canonical_title: str
    brand: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    last_price: Optional[float] = None
    lowest_price_ever: Optional[float] = None
    last_installment_count: Optional[int] = None
    last_installment_price: Optional[float] = None
    last_installment_no_interest: Optional[bool] = None
    status: str


class PriceHistoryPointOut(BaseModel):
    recorded_at: str
    price: float
    is_bug_candidate: bool
    deviation_percent: Optional[float] = None


class ProductDetail(BaseModel):
    id: int
    canonical_title: str
    brand: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    storage_gb: Optional[int] = None
    ram_gb: Optional[int] = None
    release_year: Optional[int] = None
    image_url: Optional[str] = None
    status: str
    last_price: Optional[float] = None
    lowest_price_ever: Optional[float] = None
    lowest_price_ever_at: Optional[str] = None
    last_installment_count: Optional[int] = None
    last_installment_price: Optional[float] = None
    last_installment_no_interest: Optional[bool] = None
    latest_coupon: Optional[str] = None
    latest_url: Optional[str] = None
    latest_store_domain: Optional[str] = None
    latest_link_status: Optional[str] = None
    listing_status: Optional[str] = None
    is_favorite: bool = False
    alert_enabled: bool = False
    price_history: List[PriceHistoryPointOut] = []


class DashboardSummary(BaseModel):
    products_total: int
    approved_today: int
    notified_today: int
    duplicated_today: int
    bugs_today: int
    coupons_active: int
    pending_review: int


class FavoriteStatus(BaseModel):
    product_id: int
    is_favorite: bool


class ProductAlertIn(BaseModel):
    enabled: bool = True
    max_price: Optional[float] = None
    send_to_telegram: bool = True


class ProductAlertOut(BaseModel):
    product_id: int
    enabled: bool
    max_price: Optional[float] = None
    send_to_telegram: bool


class ProductStatusOut(BaseModel):
    product_id: int
    status: str


class MergeRequest(BaseModel):
    source_product_id: int
    reason: Optional[str] = None


class MergeResult(BaseModel):
    source_product_id: int
    target_product_id: int


class ProductAdmin(BaseModel):
    id: int
    canonical_title: str
    brand: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    status: str
    merged_into_product_id: Optional[int] = None
    last_seen_at: str


class MatchQueueItem(BaseModel):
    id: int
    promotion_id: int
    status: str
    attempts: int
    extracted_specs_json: str
    candidate_products_json: Optional[str] = None
    created_at: str


class MatchQueueResolveRequest(BaseModel):
    action: str  # assign | create_new | ignore
    product_id: Optional[int] = None


class MatchQueueResolveResult(BaseModel):
    action: str
    product_id: Optional[int] = None


class CouponOut(BaseModel):
    id: int
    code: Optional[str] = None
    discount_label: Optional[str] = None
    description: Optional[str] = None
    store_name: Optional[str] = None
    store_domain: Optional[str] = None
    url: Optional[str] = None
    status: str
    source_chat_title: Optional[str] = None
    repeat_count: int
    first_seen_at: str
    last_seen_at: str


class AlertIn(BaseModel):
    name: str
    enabled: bool = True
    alert_type: str = "PRODUCT_RULE"
    required: List[str] = []
    any: List[str] = []
    exclude: List[str] = []
    max_price: Optional[float] = None
    min_discount_percent: Optional[float] = None
    bug_mode: bool = False
    min_score: int = 0
    send_to_telegram: bool = True


class AlertOut(AlertIn):
    id: Optional[int] = None
