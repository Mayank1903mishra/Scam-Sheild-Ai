import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, api } from '../api'
import type { ScanResponse } from '../types'
import { ErrorBanner } from '../components/ErrorBanner'
import { PrivacyNotice } from '../components/PrivacyNotice'

const MAX_UPLOAD_BYTES = 5 * 1024 * 1024

export function InputPage({ onResult }: { onResult: (scan: ScanResponse) => void }) {
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (loading) return
    setError(null)

    const trimmedText = text.trim()
    const trimmedUrl = url.trim()

    if (!trimmedText && !trimmedUrl && !file) {
      setError('Enter some text, a URL, or choose a screenshot first.')
      return
    }
    if (file && file.size > MAX_UPLOAD_BYTES) {
      setError('The screenshot is larger than the 5 MB limit.')
      return
    }

    setLoading(true)
    const request = (async () => {
      try {
        let scan: ScanResponse
        if (file) {
          const form = new FormData()
          form.append('file', file)
          if (trimmedText) form.append('text', trimmedText)
          if (trimmedUrl) form.append('url', trimmedUrl)
          scan = await api.uploadScan(form)
        } else {
          scan = await api.createScan({
            ...(trimmedText ? { text: trimmedText } : {}),
            ...(trimmedUrl ? { url: trimmedUrl } : {}),
          })
        }
        onResult(scan)
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message)
        } else {
          setError('Something went wrong. Please try again.')
        }
      } finally {
        setLoading(false)
      }
    })()
    void request
  }

  return (
    <section className="page">
      <h1>Check a message, link, or screenshot</h1>
      <p className="muted">
        Fill in one or more fields - you can combine text, a URL, and a
        screenshot in a single analysis.
      </p>

      <PrivacyNotice />

      <form onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="text-input">Text message</label>
          <textarea
            id="text-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste the suspicious message here..."
            maxLength={10000}
            rows={6}
            disabled={loading}
          />
          <span className="field__hint">{text.length} / 10000 characters</span>
        </div>

        <div className="field">
          <label htmlFor="url-input">URL</label>
          <input
            id="url-input"
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/offer"
            maxLength={2048}
            disabled={loading}
          />
          <span className="field__hint">
            Links are only inspected as text - the server never opens them.
          </span>
        </div>

        <div className="field">
          <label htmlFor="file-input">Screenshot (PNG, JPEG, or WebP, max 5 MB)</label>
          <input
            id="file-input"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(e) => setFile(e.target.files && e.target.files[0] ? e.target.files[0] : null)}
            disabled={loading}
          />
          {file && (
            <span className="field__hint">
              Selected: {file.name} ({Math.ceil(file.size / 1024)} KB)
            </span>
          )}
        </div>

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <button type="submit" className="button button--primary" disabled={loading}>
          {loading ? 'Analysing...' : 'Analyse'}
        </button>
        {loading && (
          <p className="loading-note" role="status">
            Analysing your input. Screenshots take a few extra seconds for OCR.
          </p>
        )}
      </form>
    </section>
  )
}
