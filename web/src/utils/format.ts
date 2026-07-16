const currencyFormatter = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return currencyFormatter.format(value)
}

export function formatInstallment(
  count: number | null | undefined,
  unitPrice: number | null | undefined,
  noInterest: boolean | null | undefined,
): string | null {
  if (!count || unitPrice === null || unitPrice === undefined) return null
  const juros = noInterest ? ' sem juros' : ''
  return `ou ${count}x de ${currencyFormatter.format(unitPrice)}${juros}`
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  // recorded_at/created_at vêm como "YYYY-MM-DD HH:MM:SS" (UTC, do SQLite)
  const iso = value.includes('T') ? value : value.replace(' ', 'T') + 'Z'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const iso = value.includes('T') ? value : value.replace(' ', 'T') + 'Z'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export const CATEGORY_LABELS: Record<string, string> = {
  smartphone: 'Smartphones',
  notebook: 'Notebooks',
  console: 'Consoles',
  tv: 'TVs',
  fone: 'Fones',
  monitor: 'Monitores',
  teclado: 'Teclados',
  mouse: 'Mouses',
  controle: 'Controles',
}
