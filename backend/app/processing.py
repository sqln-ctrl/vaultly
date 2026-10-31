import base64
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .config import settings


def extract_text(path: Path, mime_type: str) -> str:
    if mime_type == "application/pdf":
        import fitz
        with fitz.open(path) as pdf:
            return "\n".join(page.get_text("text").strip() for page in pdf if page.get_text("text").strip())
    return ""


def classify_document(text: str, filename: str) -> str:
    value = f"{text}\n{filename}".lower()
    if any(word in value for word in ("receipt", "payment received", "thank you")):
        return "Receipt"
    if "invoice" in value:
        return "Invoice"
    if any(word in value for word in ("contract", "agreement", "terms and conditions")):
        return "Contract"
    if "tax" in value or "statement" in value:
        return "Statement"
    return "Other"


def extract_fields(text: str) -> dict:
    vendor_match = re.search(r"(?:from|vendor|merchant|seller)[:\s]+([A-Za-z0-9][^\n,]{2,60})", text, re.I)
    number_match = re.search(r"(?:invoice|receipt|document|bill)\s*(?:no|number|#)?[:\s#-]*([A-Za-z0-9][A-Za-z0-9_-]{2,30})", text, re.I)
    date_match = re.search(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b", text, re.I)
    amount_match = re.search(r"(?:total|amount due|grand total|balance)[^\d]{0,20}([$€£]?\s*\d[\d,]*\.\d{2})", text, re.I)

    currency = "$" if "$" in text else "€" if "€" in text else "£" if "£" in text else None
    amount = None
    if amount_match:
        try:
            amount = float(re.sub(r"[^\d.]", "", amount_match.group(1)))
        except ValueError:
            amount = None
    return {
        "vendor": vendor_match.group(1).strip() if vendor_match else None,
        "doc_number": number_match.group(1).strip() if number_match else None,
        "issue_date": None,
        "due_date": None,
        "total_amount": amount,
        "currency": currency,
    }


def local_summary(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return "Document uploaded successfully. Text extraction did not find readable content."
    return clean[:500] + ("..." if len(clean) > 500 else "")


def _openai_request(messages: list[dict], response_format: dict | None = None) -> str | None:
    if not settings.openai_api_key:
        return None
    payload = {"model": settings.openai_model, "messages": messages, "temperature": 0.2}
    if response_format:
        payload["response_format"] = response_format
    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError):
        return None


def process_document(path: Path, mime_type: str, filename: str) -> dict:
    text = extract_text(path, mime_type)
    if mime_type.startswith("image/") and settings.openai_api_key:
        try:
            image = base64.b64encode(path.read_bytes()).decode("ascii")
            media_type = mime_type
            result = _openai_request([{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Read all visible text in this document image and return only the text."},
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image}"}},
                ],
            }])
            if result:
                text = result.strip()
        except (OSError, ValueError):
            text = ""
    fields = extract_fields(text)
    category = classify_document(text, filename)
    summary = local_summary(text)

    if settings.openai_api_key and text.strip():
        prompt = (
            "Analyze this document text. Return JSON with keys vendor, doc_number, issue_date, due_date, "
            "total_amount, currency, category, summary. Use ISO YYYY-MM-DD dates or null, numeric amount or null, "
            "currency code or null, and keep the summary under 300 characters.\n\n" + text[:12000]
        )
        result = _openai_request([{"role": "user", "content": prompt}], {"type": "json_object"})
        if result:
            try:
                ai = json.loads(result)
                fields.update({
                    "vendor": ai.get("vendor"),
                    "doc_number": ai.get("doc_number"),
                    "issue_date": ai.get("issue_date"),
                    "due_date": ai.get("due_date"),
                    "total_amount": ai.get("total_amount"),
                    "currency": ai.get("currency"),
                })
                category = ai.get("category") or category
                summary = ai.get("summary") or summary
            except json.JSONDecodeError:
                pass

    return {
        "text": text,
        "category": category[:32],
        "summary": summary[:2000],
        "fields": fields,
    }


def answer_document_question(document_text: str, document_summary: str, question: str, history: list[dict]) -> str:
    context = document_text[:16000] or document_summary or "No readable document text is available."
    system = (
        "You answer questions about one private document. Use only the supplied document context. "
        "If the answer is not supported by the document, say so clearly."
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": f"Document context:\n{context}"}]
    messages.extend(history[-8:])
    messages.append({"role": "user", "content": question})
    result = _openai_request(messages)
    if result:
        return result.strip()

    words = re.findall(r"[\w$€£.,%/-]+", context)
    if words:
        snippet = " ".join(words[:100])
        return f"I could not reach the AI service. Here is the document text available locally: {snippet}"
    return "No readable text is available for this document."
