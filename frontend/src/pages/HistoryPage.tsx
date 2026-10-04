import { useEffect, useState } from 'react'
import { ApiError, api } from '../api'
import type { ScanListItem, ScanResponse } from '../types'
import { ErrorBanner } from '../components/ErrorBanner'
import { RiskBadge } from '../components/RiskBadge'
import { InputTypeBadges, formatCategory } from '../components/format'

interface HistoryPageProps {
  onView: (scan: ScanResponse) => void
  onNewScan: () => void
}

export function HistoryPage({ onView, onNewScan }: HistoryPageProps) {
  const [items, setItems] = useState<ScanListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [viewingId, setViewingId] = useState<string | null>(null)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setItems(await api.listScans())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load history.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function handleView(id: string) {
    setError(null)
    setViewingId(id)
    try {
      onView(await api.getScan(id))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not open the scan.')
    } finally {
      setViewingId(null)
    }
  }

  async function handleDelete(id: string) {
    setError(null)
    setDeletingId(id)
    try {
      await api.deleteScan(id)
      setItems((prev) => (prev ? prev.filter((item) => item.id !== id) : prev))
      setConfirmingId(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not delete the scan.')
      setConfirmingId(null)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <section className="page">
      <div className="result-header">
        <h1>History</h1>
        <button type="button" className="button button--primary" onClick={onNewScan}>
          New analysis
        </button>
      </div>
      <p className="muted">
        Scans are kept for 30 days, then removed automatically. You can delete
        any scan now.
      </p>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {loading && <p role="status">Loading history...</p>}

      {!loading && items !== null && items.length === 0 && (
        <div className="card empty-state">
          <p>No scans yet.</p>
          <button type="button" className="button button--primary" onClick={onNewScan}>
            Analyse your first message
          </button>
        </div>
      )}

      {!loading && items !== null && items.length > 0 && (
        <ul className="history-list">
          {items.map((item) => (
            <li className="history-row" key={item.id}>
              <div className="history-row__main">
                <span className="history-row__date">
                  {new Date(item.created_at).toLocaleString()}
                </span>
                <InputTypeBadges types={item.input_types} />
                <span className="history-row__category">{formatCategory(item.category)}</span>
              </div>
              <div className="history-row__result">
                <RiskBadge band={item.risk_band} />
                <span className="history-row__score">{item.risk_score}/100</span>
              </div>
              <div className="history-row__actions">
                <button
                  type="button"
                  className="button"
                  onClick={() => void handleView(item.id)}
                  disabled={viewingId === item.id || deletingId === item.id}
                >
                  {viewingId === item.id ? 'Opening...' : 'View'}
                </button>
                {confirmingId !== item.id ? (
                  <button
                    type="button"
                    className="button button--danger"
                    onClick={() => setConfirmingId(item.id)}
                    disabled={deletingId === item.id}
                  >
                    Delete
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      className="button button--danger"
                      onClick={() => void handleDelete(item.id)}
                      disabled={deletingId === item.id}
                    >
                      {deletingId === item.id ? 'Deleting...' : 'Confirm'}
                    </button>
                    <button
                      type="button"
                      className="button"
                      onClick={() => setConfirmingId(null)}
                      disabled={deletingId === item.id}
                    >
                      Cancel
                    </button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
