import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render } from '@testing-library/react'
import { ResultPage } from '../pages/ResultPage'
import type { ScanResponse } from '../types'

afterEach(cleanup)

const XSS_SNIPPET = '<script>window.__xssExecuted = 1</script> <img src=x onerror="window.__imgExecuted=1">'

function makeScan(overrides: Partial<ScanResponse> = {}): ScanResponse {
  return {
    id: 'scan-1',
    created_at: '2026-10-04T12:00:00Z',
    input_types: ['text'],
    risk_score: 75,
    risk_band: 'HIGH',
    score_note: 'Heuristic score, not a probability; thresholds provisional.',
    category: 'FAKE_JOB',
    uncertainty: { level: 'low', reasons: ['No risk indicators detected'] },
    modules: { text: 60, url: 0, ocr_confidence: null },
    evidence: [
      {
        id: 'UPFRONT_PAYMENT',
        source: 'text',
        reason: 'Requests payment before starting work.',
        snippet: XSS_SNIPPET,
        weight: 30,
      },
    ],
    extracted: { urls: [], emails: [], phones: [], domains: [] },
    recommendations: ['Do not pay any fee.', 'Verify through the official website.'],
    disclaimer: 'Risk indicators are not proof of fraud.',
    mode: 'rules',
    ocr_text: null,
    ...overrides,
  }
}

describe('escaping of user and OCR content', () => {
  it('renders script tags from evidence snippets as literal text, never as HTML', () => {
    const { container } = render(
      <ResultPage scan={makeScan()} origin="fresh" onNewScan={vi.fn()} onHistory={vi.fn()} />,
    )

    // The dangerous markup must be visible as plain text...
    expect(container.textContent).toContain('<script>window.__xssExecuted = 1</script>')
    // ...but no script element may exist in the DOM.
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect((window as unknown as { __xssExecuted?: number }).__xssExecuted).toBeUndefined()
    expect((window as unknown as { __imgExecuted?: number }).__imgExecuted).toBeUndefined()
  })

  it('escapes HTML injected through category and uncertainty reasons', () => {
    const { container } = render(
      <ResultPage
        scan={makeScan({
          category: '<b>FAKE</b>',
          uncertainty: {
            level: 'high',
            reasons: ['<iframe src="evil"></iframe>'],
          },
        })}
        origin="fresh"
        onNewScan={vi.fn()}
        onHistory={vi.fn()}
      />,
    )

    expect(container.querySelector('b')).toBeNull()
    expect(container.querySelector('iframe')).toBeNull()
    expect(container.textContent).toContain('<b>fake</b>')
    expect(container.textContent).toContain('<iframe src="evil"></iframe>')
  })

  it('shows the provisional-score disclaimer on every result (F5)', () => {
    const { container } = render(
      <ResultPage scan={makeScan()} origin="fresh" onNewScan={vi.fn()} onHistory={vi.fn()} />,
    )

    expect(container.textContent).toContain('Risk indicators are not proof of fraud.')
    expect(container.textContent).toContain('thresholds provisional')
  })
})
