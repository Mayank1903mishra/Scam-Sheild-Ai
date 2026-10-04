# ScamShield AI

Multi-modal scam and fraud analysis tool for students. Analyzes text, URLs, and screenshots to detect risk indicators and explain findings.

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Tesseract OCR (system dependency)

### Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env
# Edit .env as needed
uvicorn app.main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Run Tests
```bash
cd backend
pytest
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