import { useParams } from 'react-router-dom'

export function ProductProfilePage() {
  const { id } = useParams()
  return (
    <div className="page">
      <h1>Perfil do produto</h1>
      <p className="page-placeholder">Produto #{id} — histórico de preço e detalhes aparecem aqui.</p>
    </div>
  )
}
