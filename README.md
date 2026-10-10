# ScamShield AI

Multi-modal scam and fraud analysis tool for students. Analyzes text, URLs, and screenshots to detect risk indicators and explain findings.

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Tesseract OCR (system dependency, used for local screenshot OCR)

### Install Tesseract OCR
The image/screenshot feature runs OCR locally with Tesseract - no API keys,
no paid services, no data leaves your machine.
- **Windows:** `winget install UB-Mannheim.TesseractOCR` (or download the
  installer from https://github.com/UB-Mannheim/tesseract/wiki). If it is
  not on PATH, set `TESSERACT_CMD` in `.env` to the full path of
  `tesseract.exe` (e.g. `C:\Program Files\Tesseract-OCR\tesseract.exe`).
- **macOS:** `brew install tesseract`
- **Linux:** `sudo apt install tesseract-ocr`

If Tesseract is missing, image uploads return a clear
`OCR_UNAVAILABLE` error instead of fake text; text and URL analysis
keep working.

### Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env     # read from backend/.env (or ../.env at the repo root)
# Edit .env as needed
uvicorn app.main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000 (talks to the backend on http://localhost:8000)
```
The UI calls `http://localhost:8000` by default, so no configuration is
needed when the backend runs on its default port. Both Vite dev ports
(`3000` from `npm run dev`, `5173` from `vite`) are in the backend CORS
allow-list. To point the UI at another backend, set `VITE_API_BASE` (e.g.
`VITE_API_BASE=http://localhost:9000 npm run dev`).

### Run Tests
```bash
# Backend (pytest)
cd backend
.venv\Scripts\python -m pytest tests/ -q      # Windows
# Frontend (vitest + typecheck + production build)
cd frontend
npm test
npm run build
```

## Project Structure
```
.
├── backend/          # FastAPI application
├── frontend/         # React + Vite application
├── docs/             # Documentation
├── .env.example      # Environment template
└── .gitignore
```

## Configuration
Copy `.env.example` to `.env` and adjust values. See `docs/API.md` for API reference.

## License
MIT