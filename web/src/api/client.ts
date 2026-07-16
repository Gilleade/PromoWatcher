import type {
  AlertDef,
  CouponOut,
  DashboardSummary,
  FavoriteStatus,
  MatchQueueItem,
  MatchQueueResolveRequest,
  MatchQueueResolveResult,
  MergeResult,
  ProductAdmin,
  ProductAlertIn,
  ProductAlertOut,
  ProductCard,
  ProductDetail,
  ProductStatusOut,
} from './types'

const BASE = '/api/v1'

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new ApiError(response.status, body.detail || response.statusText)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  feed: (params?: { category?: string; limit?: number; offset?: number }) => {
    const search = new URLSearchParams()
    if (params?.category) search.set('category', params.category)
    if (params?.limit) search.set('limit', String(params.limit))
    if (params?.offset) search.set('offset', String(params.offset))
    const qs = search.toString()
    return request<ProductCard[]>(`/feed${qs ? `?${qs}` : ''}`)
  },

  getProduct: (id: number) => request<ProductDetail>(`/products/${id}`),

  getPriceHistory: (id: number, windowDays = 30) =>
    request<ProductDetail['price_history']>(`/products/${id}/price-history?window=${windowDays}`),

  addFavorite: (id: number) => request<FavoriteStatus>(`/products/${id}/favorite`, { method: 'POST' }),
  removeFavorite: (id: number) => request<FavoriteStatus>(`/products/${id}/favorite`, { method: 'DELETE' }),
  listFavorites: () => request<ProductCard[]>('/favorites'),

  setAlert: (id: number, body: ProductAlertIn) =>
    request<ProductAlertOut>(`/products/${id}/alert`, { method: 'POST', body: JSON.stringify(body) }),

  blockProduct: (id: number) => request<ProductStatusOut>(`/products/${id}/block`, { method: 'POST' }),
  unblockProduct: (id: number) => request<ProductStatusOut>(`/products/${id}/unblock`, { method: 'POST' }),
  mergeProduct: (targetId: number, sourceProductId: number, reason?: string) =>
    request<MergeResult>(`/products/${targetId}/merge`, {
      method: 'POST',
      body: JSON.stringify({ source_product_id: sourceProductId, reason }),
    }),

  listCoupons: (status = 'ACTIVE') => request<CouponOut[]>(`/coupons?status=${status}`),

  dashboardSummary: () => request<DashboardSummary>('/dashboard/summary'),

  listAlerts: () => request<AlertDef[]>('/alerts'),
  createAlert: (body: AlertDef) => request<AlertDef>('/alerts', { method: 'POST', body: JSON.stringify(body) }),
  updateAlert: (id: number, body: AlertDef) =>
    request<AlertDef>(`/alerts/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteAlert: (id: number) => request<{ deleted: boolean; name: string }>(`/alerts/${id}`, { method: 'DELETE' }),
  toggleAlert: (id: number) => request<AlertDef>(`/alerts/${id}/toggle`, { method: 'POST' }),

  adminListProducts: (params?: { status?: string; search?: string }) => {
    const search = new URLSearchParams()
    if (params?.status) search.set('status', params.status)
    if (params?.search) search.set('search', params.search)
    const qs = search.toString()
    return request<ProductAdmin[]>(`/admin/products${qs ? `?${qs}` : ''}`)
  },
  adminMatchQueue: (status?: string) =>
    request<MatchQueueItem[]>(`/admin/match-queue${status ? `?status=${status}` : ''}`),
  adminResolveMatchQueue: (itemId: number, body: MatchQueueResolveRequest) =>
    request<MatchQueueResolveResult>(`/admin/match-queue/${itemId}/resolve`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

export { ApiError }
