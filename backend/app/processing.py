import json
import logging
import re
from pathlib import Path

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def _plain_response(text: str) -> str:
    text = text.replace("*", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(path: Path, mime_type: str) -> str:
    if mime_type == "application/pdf":
        import fitz
        with fitz.open(path) as pdf:
            return "\n".join(
                page.get_text("text").strip()
                for page in pdf
                if page.get_text("text").strip()
            )
    return ""


def classify_document(text: str, filename: str) -> str:
    value = f"{text}\n{filename}".lower()
    if any(word in value for word in ("receipt", "payment received", "thank you")):
        return "Receipt"
    if "invoice" in value:
        return "Invoice"
    if "contract" in value or "agreement" in value:
        return "Contract"
    if "tax" in value or "statement" in value:
        return "Statement"
    return "Other"


def extract_fields(text: str) -> dict:
    vendor_match = re.search(
        r"(?:from|vendor|merchant|seller)[:\s]+([A-Za-z0-9][^\n,]{2,60})",
        text,
        re.I,
    )
    number_match = re.search(
        r"(?:invoice|receipt|document|bill)\s*(?:no|number|#)?[:\s#-]*([A-Za-z0-9][A-Za-z0-9_-]{2,30})",
        text,
        re.I,
    )
    amount_match = re.search(
        r"(?:total|amount due|grand total|balance)[^\d]{0,20}([$€£]?\s*\d[\d,]*\.\d{2})",
        text,
        re.I,
    )
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


def _cohere_request(messages: list[dict], response_format: dict | None = None) -> str | None:
    if not settings.cohere_api_key:
        return None

    payload: dict = {
        "model": settings.cohere_model,
        "messages": messages,
        "stream": False,
        "temperature": 0.2,
        "max_tokens": 300,
    }
    if response_format:
        payload["response_format"] = response_format

    try:
        response = httpx.post(
            "https://api.cohere.com/v2/chat",
            headers={
                "Authorization": f"Bearer {settings.cohere_api_key.strip()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        message = data.get("message") or {}
        content = message.get("content") or []
        if isinstance(content, list):
            text = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            ).strip()
            return text or None
        if isinstance(content, str):
            return content.strip() or None
        return None
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Cohere API request failed with status %s: %s",
            exc.response.status_code,
            exc.response.text[:500],
        )
        return None
    except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError) as exc:
        logger.error("Cohere API request failed: %s", exc)
        return None


def process_document(path: Path, mime_type: str, filename: str) -> dict:
    text = extract_text(path, mime_type)
    fields = extract_fields(text)
    category = classify_document(text, filename)
    summary = local_summary(text)

    if settings.cohere_api_key and text.strip():
        prompt = (
            "Analyze this document text. Return a JSON object with keys vendor, doc_number, "
            "issue_date, due_date, total_amount, currency, category, summary. Use ISO YYYY-MM-DD "
            "dates or null, numeric amount or null, currency code or null, and keep the summary "
            "under 300 characters.\n\nGenerate JSON:\n" + text[:12000]
        )
        result = _cohere_request(
            [{"role": "user", "content": prompt}],
            {"type": "json_object"},
        )
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


def answer_vault_question(documents: list[dict], question: str, history: list[dict]) -> str:
    context_parts = []
    for document in documents:
        text = document.get("text") or document.get("summary") or "No readable text is available."
        context_parts.append(f"[Document: {document['name']}]\n{text[:6000]}")
    context = "\n\n".join(context_parts)[:24000]
    system = (
        "Answer directly and concisely in one short paragraph unless a list is necessary. "
        "Keep the response under 100 words. Do not use asterisks, markdown bullets, bold text, "
        "headings, or any other decorative formatting. "
        "For factual questions, give only the requested fact without expanding abbreviations, "
        "adding definitions, or explaining the meaning unless the question explicitly asks for one. "
        "Use only the supplied document context. If a document supports the answer, add a final "
        "line exactly in this format: Sources: filename.pdf, filename2.pdf. Do not list documents "
        "that were not used, and do not add a Sources line if no document supports the answer. "
        "Never begin the answer with phrases such as 'According to this document' or 'Based on the document'."
    )
    messages = [{"role": "system", "content": system}]
    if context:
        messages.append({"role": "user", "content": f"Vault context:\n{context}"})
    messages.extend(history[-8:])
    messages.append({"role": "user", "content": question})

    result = _cohere_request(messages)
    if result:
        return _plain_response(result)
    if context:
        source_names = [
            document["name"]
            for document in documents
            if document.get("name")
        ][:5]
        source_line = f"\nSources: {', '.join(source_names)}" if source_names else ""
        return (
            "I could not generate a complete answer right now."
            + source_line
        )
    return "Your vault has no readable document content yet."
