# Assumptions Log

Record of reversible assumptions made during development. Each entry: date, assumption, rationale, revisit trigger.

---

## 2026-10-04: Stack & Scope Decisions (Owner-Approved)

| # | Assumption | Rationale | Revisit Trigger |
|---|------------|-----------|-----------------|
| 1 | FastAPI + React + Vite + SQLite for MVP | Matches both spec docs' `[PROPOSED]` choices; zero-infra SQLite; strong ecosystems | If owner requests different stack |
| 2 | Fresh build; no pre-existing components | Workspace contains only `AGENTS.md` (1 byte placeholder) | If owner declares existing code |
| 3 | Rule-based detection only (no ML) | No licensed dataset selected; training/eval would delay MVP; rules satisfy F1–F6 | When a licensed dataset is acquired and evaluated |
| 4 | No external APIs in MVP | Spec explicitly: "None required for MVP"; avoids keys, rate limits, SSRF | If reputation/WHOIS APIs are approved |
| 5 | No authentication (anonymous, single-user local) | Spec: "SQLite, anonymous use"; avoids user mgmt complexity | If multi-user or deployment model changes |
| 6 | 30-day retention, `STORE_CONTENT=false` default, explicit consent notice | Matches `[PROPOSED]` in spec §8 and `.env.example` | If owner changes retention period or consent wording |
| 7 | Raw uploaded images deleted after OCR | Spec §8: "delete the image after OCR by default" | If retention policy changes |
| 8 | Text input max 10,000 chars; URL max 2,048 chars | Build plan §9 proposal; prevents DoS via oversized input | If different limits needed |
| 9 | Tesseract OCR available as system dependency | Spec §6: "Tesseract via pytesseract (local)"; not pip-installable | If OCR engine changes |
| 10 | Risk bands (0-30/31-60/61-80/81-100) are provisional & uncalibrated | Spec §9: "not experimentally justified; must be labelled provisional" | When calibrated with real evaluation data |
| 11 | Category selection: highest-weight matching scam type; `UNCERTAIN` if tie/conflict | Not specified in spec; reasonable default for rule engine | When category logic is formalized |
| 12 | PII masking: phone (E.164), email (RFC 5322), ID-like (Aadhaar/PAN/SSN patterns) | Spec §8 lists "phone numbers, emails, and ID-like numbers" | If jurisdiction-specific IDs added |

---

## Template for Future Entries

```
## YYYY-MM-DD: Short Title

| # | Assumption | Rationale | Revisit Trigger |
|---|------------|-----------|-----------------|
| N | ... | ... | ... |
```