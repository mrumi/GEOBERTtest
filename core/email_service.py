# ============================================================
# core/email_service.py — Transactional email via Brevo
# ============================================================
import html
import logging

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


async def send_email(to_email: str, to_name: str, subject: str, html_content: str) -> bool:
    """Send one email through Brevo. Returns False (never raises) on failure,
    so a mail outage can't break registration or leak account existence."""
    payload = {
        "sender"      : {"name": settings.BREVO_SENDER_NAME, "email": settings.BREVO_SENDER_EMAIL},
        "to"          : [{"email": to_email, "name": to_name}],
        "subject"     : subject,
        "htmlContent" : html_content,
    }
    headers = {
        "api-key"      : settings.BREVO_API_KEY,
        "accept"       : "application/json",
        "content-type" : "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(BREVO_URL, json=payload, headers=headers)
        if response.status_code >= 400:
            logger.error("Brevo send failed (%s): %s", response.status_code, response.text)
            return False
        return True
    except httpx.HTTPError as error:
        logger.error("Brevo request error: %s", error)
        return False


def _render(heading: str, body_html: str, button_label: str, link: str, footnote: str) -> str:
    return f"""
<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;color:#111">
  <h2 style="margin:0 0 16px">{heading}</h2>
  {body_html}
  <p style="margin:24px 0">
    <a href="{link}" style="background:#111;color:#fff;padding:12px 20px;border-radius:6px;text-decoration:none;display:inline-block">{button_label}</a>
  </p>
  <p style="font-size:13px;color:#555">Or paste this link into your browser:<br>{link}</p>
  <p style="font-size:13px;color:#555">{footnote}</p>
</div>"""


async def send_verification_email(to_email: str, full_name: str, token: str) -> bool:
    link = f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?token={token}"
    body = f"<p>Hi {html.escape(full_name)}, welcome to GeoBERT. Please confirm your email address to activate your account.</p>"
    footnote = f"This link expires in {settings.VERIFY_TOKEN_EXPIRE_HOURS} hours. If you didn't create an account, you can ignore this email."
    return await send_email(
        to_email, full_name, "Verify your GeoBERT email",
        _render("Confirm your email", body, "Verify email", link, footnote),
    )


async def send_password_reset_email(to_email: str, full_name: str, token: str) -> bool:
    link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
    body = f"<p>Hi {html.escape(full_name)}, we received a request to reset your GeoBERT password.</p>"
    footnote = f"This link expires in {settings.RESET_TOKEN_EXPIRE_MINUTES} minutes and works once. If you didn't request this, you can ignore this email and your password stays the same."
    return await send_email(
        to_email, full_name, "Reset your GeoBERT password",
        _render("Reset your password", body, "Reset password", link, footnote),
    )