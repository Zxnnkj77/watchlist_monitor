"""SMTP email delivery."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from config import AppConfig

LOGGER = logging.getLogger(__name__)


def send_email(config: AppConfig, subject: str, html_body: str) -> bool:
    """Send the briefing email if SMTP settings are configured."""

    if not config.email_is_configured:
        LOGGER.info("SMTP settings are incomplete; email delivery skipped")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.smtp_from
    message["To"] = config.smtp_to
    message.set_content("Your watchlist briefing is available in HTML format.")
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20) as smtp:
        if config.smtp_use_tls:
            smtp.starttls()
        if config.smtp_username and config.smtp_password:
            smtp.login(config.smtp_username, config.smtp_password)
        smtp.send_message(message)

    LOGGER.info("Sent briefing email to %s", config.smtp_to)
    return True
