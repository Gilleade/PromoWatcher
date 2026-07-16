import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import type { AlertDef } from '../api/types'

const EMPTY_FORM: AlertDef = {
  name: '',
  enabled: true,
  alert_type: 'PRODUCT_RULE',
  required: [],
  any: [],
  exclude: [],
  max_price: null,
  min_discount_percent: null,
  bug_mode: false,
  min_score: 0,
  send_to_telegram: true,
}

function toLines(terms: string[]): string {
  return terms.join('\n')
}

function fromLines(text: string): string[] {
  return text.split('\n').map((l) => l.trim()).filter(Boolean)
}

function AlertForm({
  initial,
  onSubmit,
  onCancel,
  submitLabel,
}: {
  initial: AlertDef
  onSubmit: (alert: AlertDef) => void
  onCancel?: () => void
  submitLabel: string
}) {
  const [name, setName] = useState(initial.name)
  const [enabled, setEnabled] = useState(initial.enabled)
  const [required, setRequired] = useState(toLines(initial.required))
  const [any, setAny] = useState(toLines(initial.any))
  const [exclude, setExclude] = useState(toLines(initial.exclude))
  const [maxPrice, setMaxPrice] = useState(initial.max_price?.toString() ?? '')
  const [minScore, setMinScore] = useState(initial.min_score.toString())
  const [bugMode, setBugMode] = useState(initial.bug_mode)
  const [sendToTelegram, setSendToTelegram] = useState(initial.send_to_telegram)

  const submit = () => {
    onSubmit({
      name: name.trim(),
      enabled,
      alert_type: bugMode ? 'BUG_RULE' : 'PRODUCT_RULE',
      required: fromLines(required),
      any: fromLines(any),
      exclude: fromLines(exclude),
      max_price: maxPrice ? Number(maxPrice) : null,
      min_discount_percent: initial.min_discount_percent,
      bug_mode: bugMode,
      min_score: minScore ? Number(minScore) : 0,
      send_to_telegram: sendToTelegram,
    })
  }

  return (
    <div className="section-card">
      <div className="form-grid">
        <label>
          Nome
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          Score mínimo
          <input type="number" value={minScore} onChange={(e) => setMinScore(e.target.value)} />
        </label>
        <label>
          Termos obrigatórios (um por linha)
          <textarea value={required} onChange={(e) => setRequired(e.target.value)} />
        </label>
        <label>
          Termos opcionais (um por linha)
          <textarea value={any} onChange={(e) => setAny(e.target.value)} />
        </label>
        <label>
          Termos bloqueados (um por linha)
          <textarea value={exclude} onChange={(e) => setExclude(e.target.value)} />
        </label>
        <label>
          Preço máximo (vazio = sem limite)
          <input type="number" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} />
        </label>
      </div>
      <label className="checkbox-row">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        Ativado
      </label>
      <label className="checkbox-row">
        <input type="checkbox" checked={bugMode} onChange={(e) => setBugMode(e.target.checked)} />
        Modo bug
      </label>
      <label className="checkbox-row">
        <input type="checkbox" checked={sendToTelegram} onChange={(e) => setSendToTelegram(e.target.checked)} />
        Enviar ao Telegram
      </label>
      <div style={{ marginTop: 10 }}>
        <button type="button" className="small-btn primary" onClick={submit} disabled={!name.trim()}>
          {submitLabel}
        </button>
        {onCancel && (
          <button type="button" className="small-btn" onClick={onCancel}>
            Cancelar
          </button>
        )}
      </div>
    </div>
  )
}

export function AlertsAdminPage() {
  const queryClient = useQueryClient()
  const { data: alerts, isLoading } = useQuery({ queryKey: ['alerts'], queryFn: api.listAlerts })
  const [editingId, setEditingId] = useState<number | 'new' | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['alerts'] })

  const createMutation = useMutation({
    mutationFn: (alert: AlertDef) => api.createAlert(alert),
    onSuccess: () => {
      invalidate()
      setEditingId(null)
    },
  })
  const updateMutation = useMutation({
    mutationFn: ({ id, alert }: { id: number; alert: AlertDef }) => api.updateAlert(id, alert),
    onSuccess: () => {
      invalidate()
      setEditingId(null)
    },
  })
  const toggleMutation = useMutation({
    mutationFn: (id: number) => api.toggleAlert(id),
    onSuccess: invalidate,
  })
  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteAlert(id),
    onSuccess: () => {
      invalidate()
      setConfirmDeleteId(null)
    },
  })

  return (
    <div className="page">
      <h1>Alertas</h1>
      <p className="page-placeholder" style={{ marginBottom: 16 }}>
        Whitelist global — qualquer promoção que bater com um alerta ativo é notificada no grupo de destino.
      </p>

      {editingId === 'new' ? (
        <AlertForm
          initial={EMPTY_FORM}
          submitLabel="Criar alerta"
          onSubmit={(alert) => createMutation.mutate(alert)}
          onCancel={() => setEditingId(null)}
        />
      ) : (
        <button type="button" className="small-btn primary" onClick={() => setEditingId('new')} style={{ marginBottom: 16 }}>
          + Novo alerta
        </button>
      )}

      {isLoading && <p className="page-placeholder">Carregando...</p>}
      {!isLoading && alerts?.length === 0 && <p className="page-placeholder">Nenhum alerta cadastrado ainda.</p>}

      {alerts?.map((alert) => (
        <div key={alert.id} className="section-card">
          {editingId === alert.id ? (
            <AlertForm
              initial={alert}
              submitLabel="Salvar alterações"
              onSubmit={(updated) => updateMutation.mutate({ id: alert.id!, alert: updated })}
              onCancel={() => setEditingId(null)}
            />
          ) : (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <strong>{alert.name}</strong>{' '}
                  <span className={`badge ${alert.enabled ? 'badge-green' : 'badge-yellow'}`}>
                    {alert.enabled ? 'ativado' : 'desativado'}
                  </span>
                </div>
                <div>
                  <button type="button" className="small-btn" onClick={() => toggleMutation.mutate(alert.id!)}>
                    {alert.enabled ? 'Desativar' : 'Ativar'}
                  </button>
                  <button type="button" className="small-btn" onClick={() => setEditingId(alert.id!)}>
                    Editar
                  </button>
                  {confirmDeleteId === alert.id ? (
                    <button
                      type="button"
                      className="small-btn danger"
                      onClick={() => deleteMutation.mutate(alert.id!)}
                    >
                      Confirmar exclusão
                    </button>
                  ) : (
                    <button type="button" className="small-btn" onClick={() => setConfirmDeleteId(alert.id!)}>
                      Excluir
                    </button>
                  )}
                </div>
              </div>
              <p className="page-placeholder" style={{ marginTop: 8, marginBottom: 0 }}>
                obrigatórios: {alert.required.join(', ') || '—'} · opcionais: {alert.any.join(', ') || '—'} ·
                bloqueados: {alert.exclude.join(', ') || '—'}
              </p>
            </>
          )}
        </div>
      ))}
    </div>
  )
}
