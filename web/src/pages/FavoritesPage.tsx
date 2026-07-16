import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { ProductCard } from '../components/ProductCard'

export function FavoritesPage() {
  const { data, isLoading, isError } = useQuery({ queryKey: ['favorites'], queryFn: api.listFavorites })

  return (
    <div className="page">
      <h1>Favoritos</h1>
      <p className="page-placeholder" style={{ marginBottom: 16 }}>
        Produtos que você está de olho, sem receber notificação — para isso, use o alerta no perfil do produto.
      </p>

      {isLoading && <p className="page-placeholder">Carregando...</p>}
      {isError && <p className="page-placeholder">Não foi possível carregar os favoritos.</p>}
      {!isLoading && !isError && data?.length === 0 && (
        <p className="page-placeholder">Nenhum favorito ainda — favorite um produto no perfil dele.</p>
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
