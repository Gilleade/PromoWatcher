import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { ProductCard } from '../components/ProductCard'
import { CATEGORY_LABELS } from '../utils/format'

export function FeedPage() {
  const [category, setCategory] = useState<string | undefined>(undefined)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['feed', category],
    queryFn: () => api.feed({ category, limit: 100 }),
  })

  return (
    <div className="page">
      <h1>Feed</h1>

      <div className="category-tabs">
        <button
          type="button"
          className={`category-tab${category === undefined ? ' active' : ''}`}
          onClick={() => setCategory(undefined)}
        >
          Todos
        </button>
        {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`category-tab${category === key ? ' active' : ''}`}
            onClick={() => setCategory(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {isLoading && <p className="page-placeholder">Carregando...</p>}
      {isError && <p className="page-placeholder">Não foi possível carregar o feed. A API está rodando?</p>}
      {!isLoading && !isError && data?.length === 0 && (
        <p className="page-placeholder">Nenhuma promoção capturada ainda.</p>
      )}

      {!isLoading && !isError && data && data.length > 0 && (
        <div className="grid-cards">
          {data.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      )}
    </div>
  )
}
