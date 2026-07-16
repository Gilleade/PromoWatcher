import { Link } from 'react-router-dom'
import type { ProductCard as ProductCardType } from '../api/types'
import { formatPrice } from '../utils/format'
import './ProductCard.css'

export function ProductCard({ product }: { product: ProductCardType }) {
  const isLowestEver =
    product.last_price !== null &&
    product.lowest_price_ever !== null &&
    product.last_price <= product.lowest_price_ever

  return (
    <Link to={`/produtos/${product.id}`} className="product-card">
      <div className="product-card-image">
        {product.image_url ? (
          <img src={product.image_url} alt={product.canonical_title} loading="lazy" />
        ) : (
          <span className="product-card-image-placeholder mono">sem imagem</span>
        )}
      </div>

      <div className="product-card-body">
        {product.brand && <span className="brand-tag">{product.brand}</span>}
        <h3 className="product-card-title">{product.canonical_title}</h3>

        <div className="product-card-price-row">
          <span className="price">{formatPrice(product.last_price)}</span>
          {isLowestEver && <span className="badge badge-green">menor preço</span>}
        </div>
      </div>
    </Link>
  )
}
