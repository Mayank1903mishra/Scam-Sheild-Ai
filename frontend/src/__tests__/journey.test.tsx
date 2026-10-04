import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import App from '../App'
import type { ScanListItem, ScanResponse } from '../types'

afterEach(cleanup)
afterEach(() => {
  vi.unstubAllGlobals()
})

const scanFixture: ScanResponse = {
  id: 'scan-123',
  created_at: '2026-10-04T12:00:00Z',
  input_types: ['text'],
  risk_score: 65,
  risk_band: 'HIGH',
  score_note: 'Provisional score based on weighted indicators - not proof of fraud.',
  category: 'advance_fee',
  uncertainty: {
    level: 'medium',
    reasons: ['Some indicators overlap, so scores may be double counted.'],
  },
  modules: { text: 65, url: 0, ocr_confidence: null },
  evidence: [
    {
      id: 'UPFRONT_PAYMENT',
      source: 'text',
      reason: 'Asks for payment before the job starts',
      snippet: 'Pay the registration fee',
      weight: 30,
    },
    {
      id: 'URGENCY_PRESSURE',
      source: 'text',
      reason: 'Creates artificial urgency',
      snippet: 'within 24 hours',
      weight: 20,
    },
    {
      id: 'GUARANTEED_SELECTION',
      source: 'text',
      reason: 'Promises guaranteed selection',
      snippet: 'guaranteed selection',
      weight: 15,
    },
  ],
  extracted: { urls: [], emails: [], phones: [], domains: [] },
  recommendations: ['Do not pay any advance fee.', 'Verify the sender independently.'],
  disclaimer: 'This is a heuristic aid, not proof of fraud.',
  mode: 'rules',
  ocr_text: null,
}

const historyFixture: ScanListItem[] = [
  {
    id: 'scan-123',
    created_at: '2026-10-04T12:00:00Z',
    input_types: ['text'],
    risk_score: 65,
    risk_band: 'HIGH',
    category: 'advance_fee',
  },
]

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

describe('full analysis journey', () => {
  it('submits text and shows the exact score, band, and evidence on the result page', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(scanFixture, 201))
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    expect(screen.getByText(/check a message, link, or screenshot/i)).toBeTruthy()

    fireEvent.change(screen.getByLabelText(/text message/i), {
      target: { value: 'Pay the registration fee within 24 hours for guaranteed selection' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))

    // Result page renders the fixture values verbatim (display fidelity).
    expect(await screen.findByText('Analysis result')).toBeTruthy()
    expect(screen.getByText('High risk')).toBeTruthy()
    expect(screen.getAllByText(/65/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Category: advance fee/i)).toBeTruthy()

    // Evidence list shows every indicator with its reason.
    expect(screen.getByText('Evidence (3)')).toBeTruthy()
    expect(screen.getByText('Asks for payment before the job starts')).toBeTruthy()
    expect(screen.getByText('Creates artificial urgency')).toBeTruthy()
    expect(screen.getByText('Promises guaranteed selection')).toBeTruthy()

    // Recommendations and disclaimer are present.
    expect(screen.getByText('Do not pay any advance fee.')).toBeTruthy()
    expect(screen.getByText('This is a heuristic aid, not proof of fraud.')).toBeTruthy()

    // Uncertainty reasons are shown.
    expect(screen.getByText('Some indicators overlap, so scores may be double counted.')).toBeTruthy()

    // The request hit the real endpoint path with the typed text.
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/api/v1/scans')
    expect(url).not.toContain('/upload')
    expect(JSON.parse(String(init.body))).toEqual({
      text: 'Pay the registration fee within 24 hours for guaranteed selection',
    })
  })

  it('sends feedback and confirms it was recorded', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/feedback')) {
        expect(init?.method).toBe('POST')
        return jsonResponse({ message: 'Feedback submitted' }, 200)
      }
      return jsonResponse(scanFixture, 201)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.change(screen.getByLabelText(/text message/i), {
      target: { value: 'some text to analyse' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))
    expect(await screen.findByText('Analysis result')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'This was helpful' }))
    expect(await screen.findByText('Thanks - your feedback has been recorded.')).toBeTruthy()

    const feedbackCall = fetchMock.mock.calls.find(([url]) =>
      String(url).includes('/feedback'),
    )
    expect(feedbackCall).toBeTruthy()
    const [, init] = feedbackCall as unknown as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toEqual({ helpful: true })
  })

  it('deletes a scan behind a two-step confirm and lands on history', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (init?.method === 'DELETE') {
        expect(url).toContain('/api/v1/scans/scan-123')
        return { ok: true, status: 204, json: async () => null } as Response
      }
      if (init?.method === 'POST' && !url.includes('/feedback')) {
        return jsonResponse(scanFixture, 201)
      }
      if (url.endsWith('/api/v1/scans')) {
        return jsonResponse(historyFixture)
      }
      if (url.includes('/api/v1/scans/scan-123')) {
        return jsonResponse(scanFixture)
      }
      return jsonResponse(scanFixture, 201)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.change(screen.getByLabelText(/text message/i), {
      target: { value: 'delete me after analysis' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))
    expect(await screen.findByText('Analysis result')).toBeTruthy()

    // First click only arms the confirmation.
    fireEvent.click(screen.getByRole('button', { name: 'Delete this scan' }))
    expect(screen.getByRole('button', { name: 'Yes, delete it' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Yes, delete it' }))
    expect(await screen.findByRole('heading', { name: 'History' })).toBeTruthy()
  })

  it('navigates to history, views a stored scan, and shows the retention note', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/v1/scans')) {
        return jsonResponse(historyFixture)
      }
      return jsonResponse(scanFixture)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'History' }))

    // The stored scan is listed with its score.
    expect(await screen.findByRole('button', { name: 'View' })).toBeTruthy()
    expect(screen.getByText('65/100')).toBeTruthy()
    expect(screen.getByText('High risk')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'View' }))

    // History-origin results explain what is not retained.
    expect(await screen.findByText(/Loaded from history: raw text/i)).toBeTruthy()
    // Fresh-only sections (OCR, detected details) stay hidden.
    expect(screen.queryByText(/Detected details/i)).toBeNull()
  })

  it('returns to a clean input form via New analysis', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(scanFixture, 201)))

    render(<App />)
    fireEvent.change(screen.getByLabelText(/text message/i), {
      target: { value: 'text to clear later' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))
    expect(await screen.findByText('Analysis result')).toBeTruthy()

    fireEvent.click(screen.getAllByRole('button', { name: 'New analysis' })[0])
    expect(screen.getByText(/check a message, link, or screenshot/i)).toBeTruthy()
    expect((screen.getByLabelText(/text message/i) as HTMLTextAreaElement).value).toBe('')
  })
})
