# Paras AI Innovations — Invoice Reconciliation Hub

A React + Tailwind frontend for the existing Python AI invoice / delivery receipt reconciliation engine. The Streamlit UI is replaced by a responsive single-page dashboard; the extraction and reconciliation logic remains in Python.

## Architecture

- `frontend/` — React 18, Vite, Tailwind CSS, Lucide icons.
- `backend/api.py` — FastAPI upload/reconciliation API.
- `backend/extractor.py` — existing Groq-backed structured document extraction.
- `backend/reconciler.py` — existing invoice-to-delivery-receipt comparison logic.
- `backend/sample_docs/` — original sample invoice and goods receipt PDFs.

## Run locally

### 1. Start the API

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
# Add your own GROQ_API_KEY to .env (https://console.groq.com)
uvicorn api:app --reload --port 8000
```

### 2. Start the React frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The frontend calls `http://localhost:8000` by default. For a separately hosted API, set `VITE_API_BASE_URL` in a frontend `.env` file to the API origin before running/building.

## API

- `GET /api/health` — health check.
- `GET /api/sample-files` — sample PDF metadata.
- `POST /api/reconcile` — multipart form fields `invoice_file`, `receipt_file`, `use_sample`, and optional `api_key`.

The frontend never stores uploaded PDFs. They are held in memory for the request and passed to the existing extractor. If an API key is entered in the UI, it is sent to the configured backend for that request. For production, prefer a server-side secret, configure strict `FRONTEND_ORIGINS`, add authentication/rate limits, and impose upload-size limits at the API or reverse proxy.

## Notes

- The demo accepts PDF files only.
- Sample mode uses the included Beverage invoice and GRN.
- The report export is JSON to preserve extracted fields and discrepancy details.
- `backend/.env.example` contains a placeholder only; never commit real API keys.
