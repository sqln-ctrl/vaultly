import re
from pathlib import Path


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


def process_document(path: Path, mime_type: str, filename: str) -> dict:
    text = extract_text(path, mime_type)
    fields = extract_fields(text)
    category = classify_document(text, filename)
    summary = local_summary(text)
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
    if context:
        return (
            "AI chat is not configured. I found the following context in your vault:\n\n"
            + context[:3000]
        )
    return "Your vault has no readable document content yet."
