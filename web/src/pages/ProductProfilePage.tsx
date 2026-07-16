import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client'
import { PriceHistoryChart } from '../components/PriceHistoryChart'
import { PriceSignalBar } from '../components/PriceSignalBar'
import { formatDate, formatInstallment, formatPrice } from '../utils/format'
import './ProductProfilePage.css'

export function ProductProfilePage() {
  const { id } = useParams()
  const productId = Number(id)
  const queryClient = useQueryClient()
  const [maxPriceInput, setMaxPriceInput] = useState('')

  const { data: product, isLoading, isError } = useQuery({
    queryKey: ['product', productId],
    queryFn: () => api.getProduct(productId),
    enabled: Number.isFinite(productId),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['product', productId] })

  const toggleFavorite = useMutation({
    mutationFn: () =>
      product?.is_favorite ? api.removeFavorite(productId) : api.addFavorite(productId),
    onSuccess: invalidate,
  })

  const toggleAlert = useMutation({
    mutationFn: () =>
      api.setAlert(productId, {
        enabled: !product?.alert_enabled,
        max_price: maxPriceInput ? Number(maxPriceInput) : null,
        send_to_telegram: true,
      }),
    onSuccess: invalidate,
  })

  const stats = useMemo(() => {
    if (!product || product.price_history.length === 0) return null
    const prices = product.price_history.map((p) => p.price)
    const min = Math.min(...prices)
    const max = Math.max(...prices)
    const avg = prices.reduce((sum, p) => sum + p, 0) / prices.length
    const current = product.last_price ?? prices[prices.length - 1]
    const savings = avg - current
    return { min, max, avg, current, savings }
  }, [product])

  const hasRecentBug = product?.price_history.some((p) => p.is_bug_candidate) ?? false

  const installment = product
    ? formatInstallment(
        product.last_installment_count,
        product.last_installment_price,
        product.last_installment_no_interest,
      )
    : null

  if (isLoading) return <div className="page"><p className="page-placeholder">Carregando...</p></div>
  if (isError || !product) {
    return <div className="page"><p className="page-placeholder">Produto não encontrado.</p></div>
  }

  return (
    <div className="page product-profile">
      <div className="product-profile-header">
        <div>
          {product.brand && <span className="brand-tag">{product.brand}</span>}
          <h1>{product.canonical_title}</h1>
          <div className="product-profile-tags">
            {product.category && <span className="tag">{product.category}</span>}
            {product.storage_gb && <span className="tag">{product.storage_gb}GB</span>}
            {product.ram_gb && <span className="tag">{product.ram_gb}GB RAM</span>}
            {hasRecentBug && <span className="badge badge-red">possível bug</span>}
          </div>
        </div>
        <div className="product-profile-actions">
          <button
            type="button"
            className={`action-btn${product.is_favorite ? ' active' : ''}`}
            onClick={() => toggleFavorite.mutate()}
            disabled={toggleFavorite.isPending}
          >
            {product.is_favorite ? '★ Favoritado' : '☆ Favoritar'}
          </button>
        </div>
      </div>

      <div className="product-profile-price-block">
        <div className="product-profile-price-row">
          <span className="price price-large">{formatPrice(product.last_price)}</span>
          {product.latest_store_domain && <span className="tag">{product.latest_store_domain}</span>}
          {product.latest_coupon && <span className="badge badge-yellow">cupom {product.latest_coupon}</span>}
        </div>
        {installment && <span className="installment-price-large">{installment}</span>}
      </div>

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <span className="stat-label">Menor histórico</span>
            <span className="stat-value">{formatPrice(stats.min)}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Média (30d)</span>
            <span className="stat-value">{formatPrice(stats.avg)}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Economia</span>
            <span className={`stat-value ${stats.savings > 0 ? 'signal-low' : 'signal-high'}`}>
              {stats.savings > 0 ? '-' : '+'}
              {formatPrice(Math.abs(stats.savings))}
            </span>
          </div>
        </div>
      )}

      {stats && <PriceSignalBar min={stats.min} max={stats.max} current={stats.current} />}

      <PriceHistoryChart productId={productId} />

      <div className="product-profile-section">
        <h3>Comparar preços</h3>
        {product.latest_url ? (
          <div className="store-row">
            <span>{product.latest_store_domain ?? 'Loja'}</span>
            <a href={product.latest_url} target="_blank" rel="noreferrer" className="store-link">
              Acessar →
            </a>
          </div>
        ) : (
          <p className="page-placeholder">Nenhum link disponível ainda.</p>
        )}
      </div>

      <div className="product-profile-section">
        <h3>Alerta deste produto</h3>
        <p className="page-placeholder">
          Além da whitelist global, você pode ligar um alerta só para este produto.
        </p>
        <div className="alert-form">
          <input
            type="number"
            placeholder="Preço máximo (opcional)"
            value={maxPriceInput}
            onChange={(e) => setMaxPriceInput(e.target.value)}
            className="alert-input"
          />
          <button
            type="button"
            className={`action-btn${product.alert_enabled ? ' active' : ''}`}
            onClick={() => toggleAlert.mutate()}
            disabled={toggleAlert.isPending}
          >
            {product.alert_enabled ? '🔔 Alerta ativo' : '🔕 Ativar alerta'}
          </button>
        </div>
      </div>

      {product.lowest_price_ever_at && (
        <p className="page-placeholder">
          Menor preço já visto: {formatPrice(product.lowest_price_ever)} em{' '}
          {formatDate(product.lowest_price_ever_at)}
        </p>
      )}
    </div>
  )
}
