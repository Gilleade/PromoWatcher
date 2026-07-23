import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api/client'
import { formatDate, formatPrice } from '../utils/format'
import './PriceHistoryChart.css'

const WINDOWS = [30, 60, 90] as const

export function PriceHistoryChart({ productId }: { productId: number }) {
  const [windowDays, setWindowDays] = useState<(typeof WINDOWS)[number]>(30)

  const { data, isLoading } = useQuery({
    queryKey: ['price-history', productId, windowDays],
    queryFn: () => api.getPriceHistory(productId, windowDays),
  })

  const chartData = useMemo(
    () => (data ?? []).map((point) => ({ ...point, label: formatDate(point.recorded_at) })),
    [data],
  )

  const lowestPoint = useMemo(() => {
    if (!data || data.length === 0) return null
    return data.reduce((lowest, point) => (point.price < lowest.price ? point : lowest), data[0])
  }, [data])

  return (
    <div className="price-chart-card">
      <div className="price-chart-header">
        <h3>Histórico de preço</h3>
        <div className="price-chart-window-toggle">
          {WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              className={`window-btn${windowDays === w ? ' active' : ''}`}
              onClick={() => setWindowDays(w)}
            >
              {w}d
            </button>
          ))}
        </div>
      </div>

      {isLoading && <p className="page-placeholder">Carregando histórico...</p>}
      {!isLoading && chartData.length === 0 && (
        <p className="page-placeholder">Ainda não há histórico suficiente nessa janela.</p>
      )}
      {!isLoading && chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} minTickGap={24} />
            <YAxis
              tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
              tickFormatter={(v) => formatPrice(v)}
              width={70}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-elevated)', border: '1px solid var(--border-strong)',
                borderRadius: 8, fontSize: 12,
              }}
              labelStyle={{ color: 'var(--text-secondary)' }}
              formatter={(value) => [formatPrice(Number(value)), 'Preço']}
            />
            <Line
              type="monotone"
              dataKey="price"
              stroke="var(--accent-purple)"
              strokeWidth={2}
              dot={{ r: 2 }}
              activeDot={{ r: 4 }}
            />
            {lowestPoint && (
              <ReferenceDot
                x={formatDate(lowestPoint.recorded_at)}
                y={lowestPoint.price}
                r={5}
                fill="var(--accent-green)"
                stroke="var(--bg-app)"
                label={{ value: 'menor histórico', position: 'top', fontSize: 10, fill: 'var(--accent-green)' }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
