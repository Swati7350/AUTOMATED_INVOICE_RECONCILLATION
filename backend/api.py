import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from extractor import extract_document_fields
from reconciler import reconcile

load_dotenv()
BASE_DIR = Path(__file__).parent
SAMPLES = BASE_DIR / "sample_docs"
app = FastAPI(title="Invoice Reconciliation API", version="1.0.0")
# Keep both local Vite hostnames allowed even when FRONTEND_ORIGINS is set in .env.
# CORS compares origins exactly, so localhost and 127.0.0.1 must both be listed.
_default_origins = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
}
_configured_origins = {
    origin.strip().rstrip("/")
    for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
    if origin.strip()
}
if not _configured_origins:
    raise RuntimeError(
        "FRONTEND_ORIGINS must be configured."
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_default_origins | _configured_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def model_dict(model: Any) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def report_payload(invoice: Any, receipt: Any) -> dict:
    report = reconcile(invoice, receipt)
    discrepancies = []
    for item in report.discrepancies:
        message = item.message
        lower = message.lower()
        status = "missing" if "not received" in lower or "not on invoice" in lower else "discrepancy"
        if "po number" in lower:
            status = "discrepancy"
        discrepancies.append({"product": item.product, "message": message, "status": status})
    matched = report.matched_products
    total = len(discrepancies) + len(matched)
    return {
        "summary": {
            "productsCompared": total,
            "matched": len(matched),
            "discrepancies": len(discrepancies),
            "confidence": 100 if total == 0 else round(len(matched) / total * 100),
            "isClean": report.is_clean,
        },
        "discrepancies": discrepancies,
        "matchedProducts": matched,
        "invoice": model_dict(invoice),
        "receipt": model_dict(receipt),
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "provider": "Groq", "model": "openai/gpt-oss-120b"}


@app.get("/api/sample-files")
def sample_files():
    return {
        "invoice": {"name": "Beverage-Invoice.pdf", "size": (SAMPLES / "Beverage-Invoice.pdf").stat().st_size},
        "receipt": {"name": "Beverage-GRN.pdf", "size": (SAMPLES / "Beverage-GRN.pdf").stat().st_size},
    }


@app.post("/api/reconcile")
async def reconcile_documents(
    invoice_file: UploadFile | None = File(default=None),
    receipt_file: UploadFile | None = File(default=None),
    use_sample: bool = Form(default=False),
    api_key: str | None = Form(default=None),
):
    key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
    if not key:
        raise HTTPException(status_code=400, detail="Add a Groq API key in the interface or configure GROQ_API_KEY on the server.")
    try:
        if use_sample:
            invoice_bytes = (SAMPLES / "Beverage-Invoice.pdf").read_bytes()
            receipt_bytes = (SAMPLES / "Beverage-GRN.pdf").read_bytes()
        else:
            if not invoice_file or not receipt_file:
                raise HTTPException(status_code=400, detail="Upload both an invoice PDF and a delivery receipt PDF.")
            if not invoice_file.filename.lower().endswith(".pdf") or not receipt_file.filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail="Only PDF files are supported.")
            invoice_bytes = await invoice_file.read()
            receipt_bytes = await receipt_file.read()
        if not invoice_bytes or not receipt_bytes:
            raise HTTPException(status_code=400, detail="One of the selected files is empty.")
        invoice = extract_document_fields(invoice_bytes, "invoice", key)
        receipt = extract_document_fields(receipt_bytes, "pod", key)
        return JSONResponse(report_payload(invoice, receipt))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Reconciliation failed: {str(exc)}") from exc
