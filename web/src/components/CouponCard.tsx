import type { CouponOut } from '../api/types'
import { formatDateTime } from '../utils/format'
import './CouponCard.css'

export function CouponCard({ coupon }: { coupon: CouponOut }) {
  return (
    <div className="coupon-card">
      <div className="coupon-card-badge">{coupon.discount_label ?? 'CUPOM'}</div>
      <div className="coupon-card-body">
        {coupon.code && <span className="coupon-code mono">{coupon.code}</span>}
        {coupon.description && <p className="coupon-description">{coupon.description}</p>}
        <div className="coupon-meta">
          {coupon.store_domain && <span className="tag">{coupon.store_domain}</span>}
          {coupon.repeat_count > 0 && <span className="tag">visto {coupon.repeat_count + 1}x</span>}
        </div>
        <div className="coupon-footer">
          <span className="page-placeholder">{formatDateTime(coupon.last_seen_at)}</span>
          {coupon.url && (
            <a href={coupon.url} target="_blank" rel="noreferrer" className="store-link">
              Ver oferta →
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
