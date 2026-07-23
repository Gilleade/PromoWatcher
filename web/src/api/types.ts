export interface ProductCard {
  id: number
  canonical_title: string
  brand: string | null
  model: string | null
  category: string | null
  image_url: string | null
  last_price: number | null
  lowest_price_ever: number | null
  last_installment_count: number | null
  last_installment_price: number | null
  last_installment_no_interest: boolean | null
  status: string
}

export interface PriceHistoryPoint {
  recorded_at: string
  price: number
  is_bug_candidate: boolean
  deviation_percent: number | null
}

export interface ProductDetail {
  id: number
  canonical_title: string
  brand: string | null
  model: string | null
  category: string | null
  storage_gb: number | null
  ram_gb: number | null
  release_year: number | null
  image_url: string | null
  status: string
  last_price: number | null
  lowest_price_ever: number | null
  lowest_price_ever_at: string | null
  last_installment_count: number | null
  last_installment_price: number | null
  last_installment_no_interest: boolean | null
  latest_coupon: string | null
  latest_url: string | null
  latest_store_domain: string | null
  latest_link_status: string | null
  listing_status: string | null
  is_favorite: boolean
  alert_enabled: boolean
  price_history: PriceHistoryPoint[]
}

export interface DashboardSummary {
  products_total: number
  approved_today: number
  notified_today: number
  duplicated_today: number
  bugs_today: number
  coupons_active: number
  pending_review: number
}

export interface FavoriteStatus {
  product_id: number
  is_favorite: boolean
}

export interface ProductAlertIn {
  enabled: boolean
  max_price?: number | null
  send_to_telegram?: boolean
}

export interface ProductAlertOut {
  product_id: number
  enabled: boolean
  max_price: number | null
  send_to_telegram: boolean
}

export interface ProductStatusOut {
  product_id: number
  status: string
}

export interface CouponOut {
  id: number
  code: string | null
  discount_label: string | null
  description: string | null
  store_name: string | null
  store_domain: string | null
  url: string | null
  status: string
  source_chat_title: string | null
  repeat_count: number
  first_seen_at: string
  last_seen_at: string
}

export interface AlertDef {
  id?: number | null
  name: string
  enabled: boolean
  alert_type: string
  required: string[]
  any: string[]
  exclude: string[]
  max_price: number | null
  min_discount_percent: number | null
  bug_mode: boolean
  min_score: number
  send_to_telegram: boolean
}

export interface ProductAdmin {
  id: number
  canonical_title: string
  brand: string | null
  model: string | null
  category: string | null
  status: string
  merged_into_product_id: number | null
  last_seen_at: string
}

export interface MatchQueueItem {
  id: number
  promotion_id: number
  status: string
  attempts: number
  extracted_specs_json: string
  candidate_products_json: string | null
  created_at: string
}

export interface MatchQueueResolveRequest {
  action: 'assign' | 'create_new' | 'ignore'
  product_id?: number | null
}

export interface MatchQueueResolveResult {
  action: string
  product_id: number | null
}

export interface MergeResult {
  source_product_id: number
  target_product_id: number
}
