import type { FeedbackResult, ScanListItem, ScanResponse } from './types'

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export class ApiError extends Error {
  code: string
  status: number

  constructor(message: string, code: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  let code = 'UNKNOWN_ERROR'
  let message = `Request failed (status ${response.status})`
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object') {
      const err = (body as { error?: { code?: string; message?: string } }).error
      if (err && typeof err.message === 'string') {
        message = err.message
        if (typeof err.code === 'string') code = err.code
      }
    }
  } catch {
    // Non-JSON error body: keep the generic message.
  }
  return new ApiError(message, code, response.status)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new ApiError(
      'Cannot reach the server. Make sure the backend is running.',
      'NETWORK_ERROR',
      0,
    )
  }
  if (!response.ok) {
    throw await toApiError(response)
  }
  if (response.status === 204) {
    return null as T
  }
  return (await response.json()) as T
}

export const api = {
  createScan(input: { text?: string; url?: string }): Promise<ScanResponse> {
    return request<ScanResponse>('/api/v1/scans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    })
  },

  uploadScan(form: FormData): Promise<ScanResponse> {
    return request<ScanResponse>('/api/v1/scans/upload', {
      method: 'POST',
      body: form,
    })
  },

  listScans(): Promise<ScanListItem[]> {
    return request<ScanListItem[]>('/api/v1/scans')
  },

  getScan(id: string): Promise<ScanResponse> {
    return request<ScanResponse>(`/api/v1/scans/${id}`)
  },

  deleteScan(id: string): Promise<null> {
    return request<null>(`/api/v1/scans/${id}`, { method: 'DELETE' })
  },

  submitFeedback(
    id: string,
    input: { helpful: boolean; comment?: string },
  ): Promise<FeedbackResult> {
    return request<FeedbackResult>(`/api/v1/scans/${id}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    })
  },
}
