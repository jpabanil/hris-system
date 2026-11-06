"""In-app notifications and best-effort email. Templates are company data."""

from __future__ import annotations

import logging
from typing import Any

from jinja2.sandbox import SandboxedEnvironment

from app.core.clock import utcnow
from app.core.config import get_settings
from app.shared.models import Notification, NotificationPreference, NotificationTemplate

logger = logging.getLogger(__name__)
_env = SandboxedEnvironment(autoescape=True)


async def notify(
    *,
    company_id: str,
    user_id: str,
    event_key: str,
    title: str,
    body: str,
    email: str | None = None,
    merge: dict[str, Any] | None = None,
) -> None:
    preference = await NotificationPreference.find_one(
        {"company_id": company_id, "user_id": user_id, "event_key": event_key}
    )
    in_app = True if preference is None else preference.in_app
    send_mail = True if preference is None else preference.email
    template = await NotificationTemplate.find_one(
        {"company_id": company_id, "event_key": event_key, "channel": "email", "is_active": True}
    )
    subject = title
    html = body
    if template is not None and merge is not None:
        subject = _env.from_string(template.subject).render(**merge)
        html = _env.from_string(template.body).render(**merge)
    if in_app:
        await Notification(
            company_id=company_id,
            user_id=user_id,
            event_key=event_key,
            title=subject,
            body=html,
            created_at=utcnow(),
        ).insert()
    if send_mail and email:
        await send_email(email, subject, html)


async def send_email(to: str, subject: str, html: str) -> None:
    settings = get_settings()
    try:
        from email.message import EmailMessage

        import aiosmtplib

        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(html, subtype="html")
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            start_tls=False,
        )
    except Exception:
        logger.info("email not sent to %s (%s)", to, subject)


async def unread_count(company_id: str, user_id: str) -> int:
    return await Notification.find(
        {"company_id": company_id, "user_id": user_id, "read_at": None}
    ).count()
