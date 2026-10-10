# ScamShield AI API

Base URL (local development): `http://localhost:8000`

Interactive docs are served at `/docs` when `APP_ENV=development`.

All endpoints are prefixed with `/api/v1`. Errors always use one shape:

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "file: Field required" } }
```

Every response carries an `X-Request-ID` header. The default rate limit is
`30/minute` per client and returns `429` with code `RATE_LIMITED`.

CORS allows the origins listed in `ALLOWED_ORIGINS` (comma-separated or JSON
array). Defaults cover `http://localhost:3000` and `http://localhost:5173`.

## GET /api/v1/health

```json
{ "status": "ok", "version": "0.1.0", "mode": "rules" }
```

`mode` is `demo` when `DEMO_MODE=true`, otherwise `rules`.

## POST /api/v1/scans

Analyze pasted text and/or a URL. Returns `201`.

```json
{ "text": "Congratulations, you won...", "url": "http://example.com/x" }
```

| Field  | Limits |
|--------|--------|
| `text` | optional, 1–10000 chars (whitespace-only is rejected) |
| `url`  | optional, 1–2048 chars |

At least one of `text` / `url` must be present, otherwise `422`.

## POST /api/v1/scans/upload

`multipart/form-data` with a required `file` (PNG/JPEG/WebP, max 5 MB) and
optional `text` / `url` form fields. The image is validated by content
(magic bytes, pixel limits), OCR'd locally with Tesseract, then discarded.
Returns `201`.

Failures: `400` invalid image · `413` too large · `415` unsupported type ·
`503 OCR_UNAVAILABLE` when Tesseract is missing · `422` missing field.

## GET /api/v1/scans?limit=50&offset=0

History list (newest first). Each item:

```json
{
  "id": "…uuid…",
  "created_at": "2026-10-10T21:17:23",
  "input_types": ["text"],
  "risk_score": 45,
  "risk_band": "MODERATE",
  "category": "PHISHING"
}
```

Raw content is never included.

## GET /api/v1/scans/{id}

Full detail for one scan; `404 HTTP_ERROR` when unknown. Evidence and
recommendations are recomputed deterministically from the stored rows.

## DELETE /api/v1/scans/{id}

`204` on success, `404` when unknown.

## POST /api/v1/scans/{id}/feedback

```json
{ "helpful": true, "comment": "optional, max 1000 chars" }
```

Returns `{ "message": "Feedback submitted" }`; `404` when the scan is unknown.

## Scan response

Returned by `POST /scans` and `POST /scans/upload`:

```json
{
  "id": "…uuid…",
  "created_at": "2026-10-10T21:17:23",
  "input_types": ["text", "url"],
  "risk_score": 45,
  "risk_band": "LOW | MODERATE | HIGH | VERY_HIGH | UNCERTAIN",
  "score_note": "Heuristic score, not a probability; thresholds provisional.",
  "category": "PHISHING",
  "uncertainty": { "level": "low|medium|high", "reasons": ["…"] },
  "modules": { "text": 30, "url": 0, "ocr_confidence": 0.96 },
  "evidence": [
    {
      "id": "CREDENTIAL_REQUEST",
      "source": "text | url | ocr | intel",
      "reason": "Human-readable explanation.",
      "snippet": "…PII-masked excerpt…",
      "weight": 30
    }
  ],
  "extracted": { "urls": [], "emails": [], "phones": [], "domains": [] },
  "recommendations": ["…"],
  "disclaimer": "Risk indicators are not proof of fraud. …",
  "mode": "rules",
  "sources": [
    { "source": "i4c", "status": "disabled", "checked_at": "…", "detail": "…", "evidence_count": 0 }
  ],
  "ocr_text": null
}
```

Notes:

- `risk_score == min(100, max(0, sum(evidence weights)))`. It is a heuristic
  score, not a probability.
- `evidence[].source` is `intel` for findings contributed by an external
  source adapter; those carry their own explanation text.
- `sources` reports what each external source did (`checked`, `disabled`,
  `skipped`, `unavailable`, `error`). It is returned when a scan is created
  and is not persisted, so `GET /scans/{id}` returns `[]`.
- `ocr_text` is only present on the upload response; OCR output is not stored.
- Snippets and any stored text are PII-masked before persistence.

## Error codes

| Code | Status | Meaning |
|------|--------|---------|
| `VALIDATION_ERROR` | 422 | Request body/fields rejected |
| `HTTP_ERROR` | 404/405 | Route or resource not found |
| `INVALID_IMAGE` | 400 | Empty, corrupt, or unreadable image |
| `FILE_TOO_LARGE` | 413 | Upload above `MAX_UPLOAD_MB` or pixel limit |
| `UNSUPPORTED_FILE_TYPE` | 415 | Not PNG/JPEG/WebP (checked by content) |
| `RATE_LIMITED` | 429 | Too many requests |
| `OCR_UNAVAILABLE` | 503 | Tesseract not installed/detected |
| `OCR_FAILED` | 503 | OCR ran but produced no usable output |
| `INTERNAL_ERROR` | 500 | Unexpected failure (no stack trace leaked) |

## Configuration

See `.env.example` for all settings: upload and image limits, OCR, CORS
origins, retention, `STORE_CONTENT`, `RATE_LIMIT`, and the intelligence layer
(`INTEL_LOOKUPS_ENABLED`, `INTEL_TIMEOUT_SECONDS`, `INTEL_CACHE_SECONDS`,
`GOOGLE_SAFE_BROWSING_API_KEY`). The file is read from `backend/.env` or
`../.env`.
