import logging

import httpx

from .config import settings

log = logging.getLogger("vaultly.email")


async def send_email(to: str, subject: str, text: str, html: str) -> bool:
    if not settings.resend_api_key:
        log.warning("Email delivery is not configured; message for %s is not sent. Subject: %s\n%s", to, subject, text)
        return False

    sender = settings.email_from.strip()
    if sender.lower().endswith("gmail.com>") or sender.lower().endswith("gmail.com"):
        sender = "Vaultly <onboarding@resend.dev>"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={"from": sender, "to": [to], "subject": subject, "text": text, "html": html},
            )
    except httpx.HTTPError as exc:
        log.error("Resend delivery failed for %s: %s", to, exc)
        return False
    if response.is_success:
        return True
    log.error("Resend rejected email for %s: status=%s body=%s", to, response.status_code, response.text[:500])
    return False
