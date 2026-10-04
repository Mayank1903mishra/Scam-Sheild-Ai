import type { RiskBand } from '../types'

const BAND_LABEL: Record<RiskBand, string> = {
  LOW: 'Low risk',
  MODERATE: 'Moderate risk',
  HIGH: 'High risk',
  VERY_HIGH: 'Very high risk',
  UNCERTAIN: 'Uncertain',
}

export function RiskBadge({ band }: { band: RiskBand }) {
  return (
    <span className={`risk-badge risk-badge--${band.toLowerCase()}`}>
      {BAND_LABEL[band]}
    </span>
  )
}
