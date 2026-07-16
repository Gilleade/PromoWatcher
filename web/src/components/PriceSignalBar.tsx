import { formatPrice } from '../utils/format'
import './PriceSignalBar.css'

export function PriceSignalBar({ min, max, current }: { min: number; max: number; current: number }) {
  const range = max - min
  const position = range > 0 ? ((current - min) / range) * 100 : 50
  const clamped = Math.min(100, Math.max(0, position))

  let label = 'Na média'
  let toneClass = 'signal-mid'
  if (clamped <= 25) {
    label = 'Abaixo da média'
    toneClass = 'signal-low'
  } else if (clamped >= 75) {
    label = 'Acima da média'
    toneClass = 'signal-high'
  }

  return (
    <div className="price-signal">
      <div className="price-signal-label">
        <span className="price-signal-text-label">Sinal de preço</span>
        <span className={`price-signal-tone ${toneClass}`}>{label}</span>
      </div>
      <div className="price-signal-track">
        <div className="price-signal-marker" style={{ left: `${clamped}%` }} />
      </div>
      <div className="price-signal-range">
        <span>MÍN. {formatPrice(min)}</span>
        <span>MÁX. {formatPrice(max)}</span>
      </div>
    </div>
  )
}
