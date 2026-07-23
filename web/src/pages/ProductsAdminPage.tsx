import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import type { MatchQueueResolveRequest } from '../api/types'

function ProductsSection() {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState('ACTIVE')
  const [search, setSearch] = useState('')
  const [mergeInputs, setMergeInputs] = useState<Record<number, string>>({})

  const { data: products, isLoading } = useQuery({
    queryKey: ['admin-products', status, search],
    queryFn: () => api.adminListProducts({ status: status || undefined, search: search || undefined }),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin-products'] })

  const blockMutation = useMutation({
    mutationFn: (id: number) => api.blockProduct(id),
    onSuccess: invalidate,
  })
  const unblockMutation = useMutation({
    mutationFn: (id: number) => api.unblockProduct(id),
    onSuccess: invalidate,
  })
  const mergeMutation = useMutation({
    mutationFn: ({ targetId, sourceId }: { targetId: number; sourceId: number }) =>
      api.mergeProduct(targetId, sourceId),
    onSuccess: invalidate,
  })

  return (
    <div className="section-card">
      <h2>Produtos</h2>
      <div className="filter-row">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="ACTIVE">Ativos</option>
          <option value="BLOCKED">Bloqueados</option>
          <option value="MERGED">Mesclados</option>
          <option value="">Todos</option>
        </select>
        <input placeholder="Buscar por título..." value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {isLoading && <p className="page-placeholder">Carregando...</p>}
      {!isLoading && products?.length === 0 && <p className="page-placeholder">Nenhum produto encontrado.</p>}

      {products && products.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Título</th>
              <th>Marca</th>
              <th>Status</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id}>
                <td className="mono">{p.id}</td>
                <td>{p.canonical_title}</td>
                <td>{p.brand ?? '—'}</td>
                <td>{p.status}</td>
                <td>
                  {p.status === 'BLOCKED' ? (
                    <button type="button" className="small-btn" onClick={() => unblockMutation.mutate(p.id)}>
                      Desbloquear
                    </button>
                  ) : (
                    p.status === 'ACTIVE' && (
                      <button type="button" className="small-btn" onClick={() => blockMutation.mutate(p.id)}>
                        Bloquear
                      </button>
                    )
                  )}
                  {p.status === 'ACTIVE' && (
                    <>
                      <input
                        type="number"
                        placeholder="ID duplicado"
                        style={{ width: 90 }}
                        value={mergeInputs[p.id] ?? ''}
                        onChange={(e) => setMergeInputs((prev) => ({ ...prev, [p.id]: e.target.value }))}
                      />
                      <button
                        type="button"
                        className="small-btn"
                        disabled={!mergeInputs[p.id]}
                        onClick={() =>
                          mergeMutation.mutate({ targetId: p.id, sourceId: Number(mergeInputs[p.id]) })
                        }
                      >
                        Mesclar
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function MatchQueueSection() {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState('PENDING')
  const [assignInputs, setAssignInputs] = useState<Record<number, string>>({})

  const { data: items, isLoading } = useQuery({
    queryKey: ['match-queue', status],
    queryFn: () => api.adminMatchQueue(status || undefined),
  })

  const resolveMutation = useMutation({
    mutationFn: ({ id, body }: { id: number; body: MatchQueueResolveRequest }) =>
      api.adminResolveMatchQueue(id, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['match-queue'] }),
  })

  return (
    <div className="section-card">
      <h2>Fila de revisão de produtos</h2>
      <div className="filter-row">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="PENDING">Pendentes</option>
          <option value="NEEDS_HUMAN">Precisa de revisão humana</option>
          <option value="DONE">Resolvidos</option>
          <option value="">Todos</option>
        </select>
      </div>

      {isLoading && <p className="page-placeholder">Carregando...</p>}
      {!isLoading && items?.length === 0 && <p className="page-placeholder">Fila vazia.</p>}

      {items?.map((item) => {
        const specs = JSON.parse(item.extracted_specs_json)
        return (
          <div key={item.id} className="section-card" style={{ marginBottom: 10 }}>
            <p style={{ margin: 0, fontSize: 12 }}>
              <strong>Item #{item.id}</strong> · promoção #{item.promotion_id} · {item.status} ·{' '}
              {item.attempts} tentativa(s)
            </p>
            <p className="page-placeholder" style={{ fontSize: 12 }}>
              specs extraídas: marca={specs.brand ?? '—'}, modelo={specs.model ?? '—'}, armazenamento=
              {specs.storage_gb ?? '—'}GB
            </p>
            {(item.status === 'PENDING' || item.status === 'NEEDS_HUMAN') && (
              <div className="filter-row">
                <input
                  type="number"
                  placeholder="ID do produto (assign)"
                  style={{ width: 150 }}
                  value={assignInputs[item.id] ?? ''}
                  onChange={(e) => setAssignInputs((prev) => ({ ...prev, [item.id]: e.target.value }))}
                />
                <button
                  type="button"
                  className="small-btn"
                  disabled={!assignInputs[item.id]}
                  onClick={() =>
                    resolveMutation.mutate({
                      id: item.id,
                      body: { action: 'assign', product_id: Number(assignInputs[item.id]) },
                    })
                  }
                >
                  Atribuir a produto existente
                </button>
                <button
                  type="button"
                  className="small-btn"
                  onClick={() => resolveMutation.mutate({ id: item.id, body: { action: 'create_new' } })}
                >
                  Criar produto novo
                </button>
                <button
                  type="button"
                  className="small-btn"
                  onClick={() => resolveMutation.mutate({ id: item.id, body: { action: 'ignore' } })}
                >
                  Ignorar
                </button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export function ProductsAdminPage() {
  return (
    <div className="page">
      <h1>Admin de produtos</h1>
      <ProductsSection />
      <MatchQueueSection />
    </div>
  )
}
