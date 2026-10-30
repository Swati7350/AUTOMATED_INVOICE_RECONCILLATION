"""
extractor.py
------------
Extracts text from a PDF using PyMuPDF, then sends it to Groq
(openai/gpt-oss-120b) for structured JSON extraction.

No vision/image step needed — PyMuPDF pulls the text layer directly,
which works for all machine-generated / digital PDFs (invoices, PODs).
"""

import json
import re
from typing import Literal

import fitz  # PyMuPDF
from groq import Groq
from pydantic import BaseModel, Field


# ── Groq model config ──────────────────────────────────────────────────────────
PRIMARY_MODEL  = "openai/gpt-oss-120b"   # best quality, free tier
FALLBACK_MODEL = "openai/gpt-oss-20b"    # faster / cheaper fallback


# ── Pydantic schema ────────────────────────────────────────────────────────────

class LineItem(BaseModel):
    description: str = ""
    size: str = ""
    volume_liters: str = ""
    quantity: str = ""
    unit_price: str = ""
    subtotal: str = ""


class DocumentFields(BaseModel):
    document_type: Literal["invoice", "delivery_receipt", "unknown"] = "unknown"
    po_number: str = ""
    invoice_number: str = ""
    date: str = ""
    vendor_name: str = ""
    buyer_name: str = ""
    shipping_origin: str = ""
    shipping_destination: str = ""
    line_items: list[LineItem] = Field(default_factory=list)
    total_amount: str = ""
    currency: str = ""
    notes: str = ""


# ── System prompts ─────────────────────────────────────────────────────────────

INVOICE_SYSTEM_PROMPT = """
You are a precise document extraction AI specialized in commercial invoices.
You will receive the raw text content of an invoice document.
Extract ALL structured data and return it as a single valid JSON object.

Rules:
1. Extract EVERY line item — do not skip any row in the products/services table.
2. For numeric fields (unit_price, subtotal, volume_liters, quantity) preserve
   the original formatting including currency symbols and units.
3. If a field is not present in the document, return an empty string "".
4. shipping_destination = the city/region the goods are shipped TO.
5. shipping_origin = the city/region the goods are shipped FROM.
6. document_type must always be "invoice".
7. Return ONLY valid JSON — no markdown fences, no explanation, no prose.

JSON schema to return:
{
  "document_type": "invoice",
  "po_number": "",
  "invoice_number": "",
  "date": "",
  "vendor_name": "",
  "buyer_name": "",
  "shipping_origin": "",
  "shipping_destination": "",
  "line_items": [
    {
      "description": "",
      "size": "",
      "volume_liters": "",
      "quantity": "",
      "unit_price": "",
      "subtotal": ""
    }
  ],
  "total_amount": "",
  "currency": "",
  "notes": ""
}
"""

POD_SYSTEM_PROMPT = """
You are a precise document extraction AI specialized in Proof of Delivery (POD)
and Delivery Receipt documents.
You will receive the raw text content of a delivery receipt / POD document.
Extract ALL structured data and return it as a single valid JSON object.

Rules:
1. Extract EVERY line item — do not skip any row in the delivery table.
2. For numeric fields (unit_price, subtotal, volume_liters, quantity) preserve
   the original formatting including units.
3. If a field is not present in the document, return an empty string "".
4. shipping_destination = the delivery city/location.
5. shipping_origin = the dispatch/pickup city/location.
6. document_type must always be "delivery_receipt".
7. po_number = the PO or reference number on the delivery receipt.
8. Return ONLY valid JSON — no markdown fences, no explanation, no prose.

JSON schema to return:
{
  "document_type": "delivery_receipt",
  "po_number": "",
  "invoice_number": "",
  "date": "",
  "vendor_name": "",
  "buyer_name": "",
  "shipping_origin": "",
  "shipping_destination": "",
  "line_items": [
    {
      "description": "",
      "size": "",
      "volume_liters": "",
      "quantity": "",
      "unit_price": "",
      "subtotal": ""
    }
  ],
  "total_amount": "",
  "currency": "",
  "notes": ""
}
"""


# ── PDF → text ─────────────────────────────────────────────────────────────────

def pdf_to_text(pdf_bytes: bytes) -> str:
    """
    Extract the full text layer from a PDF using PyMuPDF.
    Returns a single string with all pages concatenated.
    Works for all digitally-generated PDFs (invoices, PODs, etc).
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_text = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if text.strip():
            pages_text.append(f"--- Page {i + 1} ---\n{text}")
    doc.close()

    if not pages_text:
        raise ValueError(
            "No text could be extracted from this PDF. "
            "It may be a scanned image-only PDF. "
            "Please upload a digitally-generated PDF."
        )

    return "\n\n".join(pages_text)


# ── Groq LLM call ──────────────────────────────────────────────────────────────

def extract_document_fields(
    pdf_bytes: bytes,
    doc_type: Literal["invoice", "pod"],
    groq_api_key: str,
) -> DocumentFields:
    """
    Extract structured fields from a PDF using Groq LLM.
    Falls back to FALLBACK_MODEL if PRIMARY_MODEL fails.
    """
    pdf_text = pdf_to_text(pdf_bytes)
    system_prompt = INVOICE_SYSTEM_PROMPT if doc_type == "invoice" else POD_SYSTEM_PROMPT

    client = Groq(api_key=groq_api_key)

    user_message = f"Here is the document text to extract from:\n\n{pdf_text}"

    # Try primary model first, then fallback
    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                max_tokens=4096,
                temperature=0,
            )
            raw_text = response.choices[0].message.content.strip()
            parsed   = _safe_parse_json(raw_text)
            return DocumentFields(**parsed)

        except Exception as e:
            if model == FALLBACK_MODEL:
                raise RuntimeError(
                    f"Both Groq models failed. Last error: {e}"
                ) from e
            # Try fallback silently
            continue


# ── JSON parsing helper ────────────────────────────────────────────────────────

def _safe_parse_json(text: str) -> dict:
    """
    Parse JSON from the model response.
    Strips markdown fences if the model includes them despite instructions.
    """
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$",          "", text, flags=re.MULTILINE)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Groq did not return valid JSON.\n\nRaw response:\n{text}\n\nError: {e}"
        )
