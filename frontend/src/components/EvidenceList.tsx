import type { EvidenceItem } from '../types'

export function EvidenceList({ evidence }: { evidence: EvidenceItem[] }) {
  if (evidence.length === 0) {
    return <p className="muted">No risk indicators found in your input.</p>
  }
  return (
    <ul className="evidence-list">
      {evidence.map((item, index) => (
        <li className="evidence-card" key={`${item.id}-${index}`}>
          <div className="evidence-card__head">
            <span className={`source-tag source-tag--${item.source}`}>
              {item.source === 'ocr' ? 'OCR' : item.source}
            </span>
            <strong>{item.reason}</strong>
            <span className="evidence-card__weight" title="Indicator weight">
              {item.weight > 0 ? `+${item.weight}` : item.weight}
            </span>
          </div>
          <blockquote className="evidence-card__snippet">{item.snippet}</blockquote>
        </li>
      ))}
    </ul>
  )
}
