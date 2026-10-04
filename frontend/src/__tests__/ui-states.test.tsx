import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { InputPage } from '../pages/InputPage'
import { HistoryPage } from '../pages/HistoryPage'

afterEach(cleanup)

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('loading states', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading state while the analysis request is pending', async () => {
    const pending = deferred<Response>()
    vi.stubGlobal('fetch', vi.fn(() => pending.promise))

    render(<InputPage onResult={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/text message/i), {
      target: { value: 'Pay the registration fee now!' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))

    const status = await screen.findByRole('status')
    expect(status.textContent).toContain('Analysing your input')
    const analyseButton = screen.getByRole('button', { name: 'Analysing...' }) as HTMLButtonElement
    expect(analyseButton.disabled).toBe(true)
  })

  it('shows a loading state while history loads', async () => {
    const pending = deferred<Response>()
    vi.stubGlobal('fetch', vi.fn(() => pending.promise))

    render(<HistoryPage onView={vi.fn()} onNewScan={vi.fn()} />)
    const status = await screen.findByRole('status')
    expect(status.textContent).toContain('Loading history')
  })
})

describe('error states', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the backend error message clearly after a failed analysis', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        ({
          ok: false,
          status: 429,
          json: async () => ({
            error: { code: 'RATE_LIMIT', message: 'Too many requests. Please wait a moment.' },
          }),
        }) as Response,
      ),
    )

    render(<InputPage onResult={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/text message/i), {
      target: { value: 'hello there' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Too many requests. Please wait a moment.')
  })

  it('shows a clear message when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))

    render(<InputPage onResult={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/text message/i), {
      target: { value: 'hello there' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Cannot reach the server')
  })

  it('shows an error when history fails to load', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        ({
          ok: false,
          status: 500,
          json: async () => ({
            error: { code: 'INTERNAL_ERROR', message: 'An unexpected error occurred' },
          }),
        }) as Response,
      ),
    )

    render(<HistoryPage onView={vi.fn()} onNewScan={vi.fn()} />)
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('An unexpected error occurred')
  })

  it('validates locally before calling the server', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(<InputPage onResult={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Enter some text, a URL, or choose a screenshot')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
