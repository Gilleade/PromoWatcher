import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { CouponCard } from '../components/CouponCard'

export function CouponsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['coupons'],
    queryFn: () => api.listCoupons('ACTIVE'),
  })

  return (
    <div className="page">
      <h1>Cupons</h1>
      <p className="page-placeholder" style={{ marginBottom: 16 }}>
        Cupons publicados sem um produto específico associado.
      </p>

      {isLoading && <p className="page-placeholder">Carregando...</p>}
      {isError && <p className="page-placeholder">Não foi possível carregar os cupons.</p>}
      {!isLoading && !isError && data?.length === 0 && (
        <p className="page-placeholder">Nenhum cupom solto capturado ainda.</p>
      )}
      {!isLoading && !isError && data && data.length > 0 && (
        <div className="coupon-list">
          {data.map((coupon) => (
            <CouponCard key={coupon.id} coupon={coupon} />
          ))}
        </div>
      )}
    </div>
  )
}
