import { useState } from 'react'
import { ApiError, api } from '../api'
import type { ScanResponse } from '../types'
import { ErrorBanner } from '../components/ErrorBanner'
import { EvidenceList } from '../components/EvidenceList'
import { ModuleBreakdown } from '../components/ModuleBreakdown'
import { RiskBadge } from '../components/RiskBadge'
import { InputTypeBadges, formatCategory } from '../components/format'

interface ResultPageProps {
  scan: ScanResponse
  /** 'fresh' = analysis response in this session; 'history' = loaded from stored scans. */
  origin: 'fresh' | 'history'
  onNewScan: () => void
  onHistory: () => void
}

export function ResultPage({ scan, origin, onNewScan, onHistory }: ResultPageProps) {
  const [feedbackGiven, setFeedbackGiven] = useState(false)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)
  const [comment, setComment] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const hasExtracted =
    scan.extracted.urls.length > 0 ||
    scan.extracted.emails.length > 0 ||
    scan.extracted.phones.length > 0 ||
    scan.extracted.domains.length > 0

  async function sendFeedback(helpful: boolean) {
    setFeedbackError(null)
    try {
      await api.submitFeedback(scan.id, {
        helpful,
        ...(comment.trim() ? { comment: comment.trim() } : {}),
      })
      setFeedbackGiven(true)
    } catch (err) {
      setFeedbackError(err instanceof ApiError ? err.message : 'Could not send feedback.')
    }
  }

  async function handleDelete() {
    setDeleteError(null)
    setDeleting(true)
    try {
      await api.deleteScan(scan.id)
      onHistory()
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : 'Could not delete the scan.')
      setConfirmDelete(false)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <section className="page">
      <div className="result-header">
        <h1>Analysis result</h1>
        <div className="result-header__meta">
          <InputTypeBadges types={scan.input_types} />
          <span className="muted">{new Date(scan.created_at).toLocaleString()}</span>
          {scan.mode === 'demo' && <span className="demo-badge">DEMO</span>}
        </div>
      </div>

      <div className={`risk-card risk-card--${scan.risk_band.toLowerCase()}`}>
        <div className="risk-card__main">
          <RiskBadge band={scan.risk_band} />
          <span className="risk-card__score">
            {scan.risk_score}
            <span className="risk-card__score-max"> / 100</span>
          </span>
        </div>
        <p className="risk-card__category">Category: {formatCategory(scan.category)}</p>
        <p className="risk-card__note">{scan.score_note}</p>
      </div>

      <div className="card">
        <h2>Confidence and uncertainty</h2>
        <p>
          Level: <strong>{scan.uncertainty.level}</strong>
        </p>
        {scan.uncertainty.reasons.length > 0 ? (
          <ul className="uncertainty-list">
            {scan.uncertainty.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">No uncertainty flags.</p>
        )}
      </div>

      <div className="card">
        <h2>Module breakdown</h2>
        <ModuleBreakdown modules={scan.modules} />
      </div>

      <div className="card">
        <h2>Evidence ({scan.evidence.length})</h2>
        <EvidenceList evidence={scan.evidence} />
      </div>

      {origin === 'fresh' && scan.ocr_text !== null && (
        <div className="card">
          <h2>Text extracted from your screenshot (OCR)</h2>
          {scan.modules.ocr_confidence !== null && (
            <p className="muted">
              OCR confidence: {Math.round(scan.modules.ocr_confidence * 100)}%
            </p>
          )}
          <blockquote className="ocr-output">{scan.ocr_text || '(no text was found in the image)'}</blockquote>
        </div>
      )}

      {origin === 'fresh' && hasExtracted && (
        <div className="card">
          <h2>Detected details</h2>
          {scan.extracted.urls.length > 0 && (
            <div className="extracted-group">
              <h3>URLs</h3>
              <ul>{scan.extracted.urls.map((u) => <li key={u}>{u}</li>)}</ul>
            </div>
          )}
          {scan.extracted.emails.length > 0 && (
            <div className="extracted-group">
              <h3>Emails</h3>
              <ul>{scan.extracted.emails.map((e) => <li key={e}>{e}</li>)}</ul>
            </div>
          )}
          {scan.extracted.phones.length > 0 && (
            <div className="extracted-group">
              <h3>Phone numbers</h3>
              <ul>{scan.extracted.phones.map((p) => <li key={p}>{p}</li>)}</ul>
            </div>
          )}
          {scan.extracted.domains.length > 0 && (
            <div className="extracted-group">
              <h3>Domains</h3>
              <ul>{scan.extracted.domains.map((d) => <li key={d}>{d}</li>)}</ul>
            </div>
          )}
        </div>
      )}

      {origin === 'history' && (
        <p className="muted retention-note">
          Loaded from history: raw text, OCR output, and detected contact
          details are not retained for privacy. The summary, evidence, and
          recommendations above are shown.
        </p>
      )}

      <div className="card">
        <h2>Recommended actions</h2>
        <ol className="recommendations">
          {scan.recommendations.map((rec) => (
            <li key={rec}>{rec}</li>
          ))}
        </ol>
      </div>

      <p className="disclaimer" role="note">
        {scan.disclaimer}
      </p>

      <div className="card">
        <h2>Feedback</h2>
        {feedbackGiven ? (
          <p role="status">Thanks - your feedback has been recorded.</p>
        ) : (
          <>
            <div className="feedback-actions">
              <button
                type="button"
                className="button"
                onClick={() => void sendFeedback(true)}
              >
                This was helpful
              </button>
              <button
                type="button"
                className="button"
                onClick={() => void sendFeedback(false)}
              >
                Result was wrong
              </button>
            </div>
            <div className="field">
              <label htmlFor="feedback-comment">Optional comment</label>
              <input
                id="feedback-comment"
                type="text"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                maxLength={1000}
                placeholder="What was right or wrong?"
              />
            </div>
            {feedbackError && <ErrorBanner message={feedbackError} />}
          </>
        )}
      </div>

      <div className="result-actions">
        <button type="button" className="button" onClick={onNewScan}>
          New analysis
        </button>
        <button type="button" className="button" onClick={onHistory}>
          History
        </button>
        {!confirmDelete ? (
          <button
            type="button"
            className="button button--danger"
            onClick={() => setConfirmDelete(true)}
          >
            Delete this scan
          </button>
        ) : (
          <span className="delete-confirm">
            <button
              type="button"
              className="button button--danger"
              onClick={() => void handleDelete()}
              disabled={deleting}
            >
              {deleting ? 'Deleting...' : 'Yes, delete it'}
            </button>
            <button
              type="button"
              className="button"
              onClick={() => setConfirmDelete(false)}
              disabled={deleting}
            >
              Cancel
            </button>
          </span>
        )}
        {deleteError && <ErrorBanner message={deleteError} />}
      </div>
    </section>
  )
}
