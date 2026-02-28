"""Notification services for PagerDuty and Email alerts."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_pagerduty_alert(title: str, body: str, severity: str = "info") -> bool:
    """Create a PagerDuty event via Events API v2."""
    if not settings.pagerduty_api_key:
        logger.warning("PagerDuty API key not configured, skipping alert")
        return False

    payload = {
        "routing_key": settings.pagerduty_api_key,
        "event_action": "trigger",
        "payload": {
            "summary": title,
            "source": "finmonitor",
            "severity": severity,
            "custom_details": {"body": body},
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("PagerDuty alert sent: %s", title)
            return True
    except httpx.HTTPError:
        logger.exception("Failed to send PagerDuty alert")
        return False


async def send_email_alert(to_address: str, subject: str, body: str) -> bool:
    """Send an email alert via SMTP (AWS SES compatible)."""
    if not settings.smtp_host or not settings.smtp_user:
        logger.warning("SMTP not configured, skipping email")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = to_address
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.email_from, [to_address], msg.as_string())
        logger.info("Email sent to %s: %s", to_address, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_address)
        return False


async def send_reminder(notify_via: str, address: str, title: str, body: str) -> bool:
    """Route a reminder to the appropriate notification channel."""
    if notify_via == "pagerduty":
        return await send_pagerduty_alert(title, body)
    elif notify_via == "email":
        return await send_email_alert(address, title, body)
    else:
        logger.error("Unknown notification channel: %s", notify_via)
        return False
