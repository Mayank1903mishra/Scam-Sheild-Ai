import type { ModuleScores } from '../types'

function ScoreBar({ label, score }: { label: string; score: number }) {
  return (
    <div className="module-row">
      <span className="module-row__label">{label}</span>
      <span className="module-row__bar" aria-hidden="true">
        <span
          className="module-row__fill"
          style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
        />
      </span>
      <span className="module-row__value">{score}</span>
    </div>
  )
}

export function ModuleBreakdown({ modules }: { modules: ModuleScores }) {
  return (
    <div className="module-breakdown">
      <ScoreBar label="Text indicators" score={modules.text} />
      <ScoreBar label="URL indicators" score={modules.url} />
      <div className="module-row">
        <span className="module-row__label">OCR confidence</span>
        <span className="module-row__value">
          {modules.ocr_confidence === null ? (
            <span className="muted" title="The image is deleted after OCR; the confidence value is not stored.">
              not stored
            </span>
          ) : (
            `${Math.round(modules.ocr_confidence * 100)}%`
          )}
        </span>
      </div>
    </div>
  )
}
