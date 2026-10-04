import { afterEach, describe, expect, it, vi } from 'vitest'
import { API_BASE, ApiError, api } from '../api'

describe('api client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('maps the backend error shape to an ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        ({
          ok: false,
          status: 413,
          json: async () => ({
            error: { code: 'FILE_TOO_LARGE', message: 'File exceeds the 5 MB upload limit' },
          }),
        }) as Response,
      ),
    )

    await expect(api.createScan({ text: 'hello' })).rejects.toMatchObject({
      code: 'FILE_TOO_LARGE',
      status: 413,
      message: 'File exceeds the 5 MB upload limit',
    })
  })

  it('returns a friendly message when the server is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))

    const error = await api.listScans().catch((err: unknown) => err)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe('NETWORK_ERROR')
    expect((error as ApiError).message).toContain('backend is running')
  })

  it('resolves DELETE (204) to null', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 204 }) as Response))

    await expect(api.deleteScan('some-id')).resolves.toBeNull()
  })

  it('posts JSON to the scans endpoint', async () => {
    const fetchMock = vi.fn(async () =>
      ({
        ok: true,
        status: 201,
        json: async () => ({ id: 'x' }),
      }) as Response,
    )
    vi.stubGlobal('fetch', fetchMock)

    await api.createScan({ text: 'suspicious message' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`${API_BASE}/api/v1/scans`)
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({ text: 'suspicious message' })
  })

  it('sends FormData without a JSON content-type header', async () => {
    const fetchMock = vi.fn(async () =>
      ({ ok: true, status: 201, json: async () => ({ id: 'x' }) }) as Response,
    )
    vi.stubGlobal('fetch', fetchMock)

    const form = new FormData()
    form.append('file', new Blob(['x'], { type: 'image/png' }), 'shot.png')
    await api.uploadScan(form)

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`${API_BASE}/api/v1/scans/upload`)
    expect(init.body).toBeInstanceOf(FormData)
    const headers = init.headers as Record<string, string> | undefined
    expect(headers?.['Content-Type']).toBeUndefined()
  })
})
