"""Email notification service using Resend.com API.

Sends job completion/failure emails to users who have opted in.
Silently skips when RESEND_API_KEY is not set.
"""

from __future__ import annotations

import logging
import os

from archiveinator.web.models import ArchiveJob

logger = logging.getLogger(__name__)


def _get_api_key() -> str | None:
    """Return the Resend API key or None if not configured."""
    return os.environ.get("RESEND_API_KEY") or None


def _get_from_addr() -> str:
    """Return the configured from address or a default."""
    return os.environ.get("RESEND_FROM", "archiveinator <onboarding@resend.dev>")


def _build_job_complete_email(job: ArchiveJob) -> tuple[str, str]:
    """Build subject and HTML body for a completed job notification."""
    url = job.url or ""
    title = job.title or url
    duration = f"{job.duration_seconds:.1f}s" if job.duration_seconds else "N/A"
    paywall_info = "Yes" if job.paywalled else "No"
    bypass_info = job.bypass_method or "N/A"
    partial_info = "Yes (partial capture)" if job.is_partial else "No"

    subject = f"Archive complete: {title[:80]}"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2>Archive Complete</h2>
  <table style="width: 100%; border-collapse: collapse;">
    <tr><td style="padding: 8px; color: #666;">URL</td>
        <td style="padding: 8px;"><a href="{url}">{url[:120]}</a></td></tr>
    <tr><td style="padding: 8px; color: #666;">Title</td>
        <td style="padding: 8px;"><strong>{title}</strong></td></tr>
    <tr><td style="padding: 8px; color: #666;">Duration</td>
        <td style="padding: 8px;">{duration}</td></tr>
    <tr><td style="padding: 8px; color: #666;">Paywall detected</td>
        <td style="padding: 8px;">{paywall_info}</td></tr>
    <tr><td style="padding: 8px; color: #666;">Bypass method</td>
        <td style="padding: 8px;">{bypass_info}</td></tr>
    <tr><td style="padding: 8px; color: #666;">Partial capture</td>
        <td style="padding: 8px;">{partial_info}</td></tr>
  </table>
</body>
</html>"""
    return subject, html


def _build_job_failed_email(job: ArchiveJob) -> tuple[str, str]:
    """Build subject and HTML body for a failed job notification."""
    url = job.url or ""
    title = job.title or url
    error = job.error or "Unknown error"

    subject = f"Archive failed: {title[:80]}"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2>Archive Failed</h2>
  <table style="width: 100%; border-collapse: collapse;">
    <tr><td style="padding: 8px; color: #666;">URL</td>
        <td style="padding: 8px;"><a href="{url}">{url[:120]}</a></td></tr>
    <tr><td style="padding: 8px; color: #666;">Title</td>
        <td style="padding: 8px;"><strong>{title}</strong></td></tr>
    <tr><td style="padding: 8px; color: #666;">Error</td>
        <td style="padding: 8px; color: #cc0000;">{error[:200]}</td></tr>
  </table>
</body>
</html>"""
    return subject, html


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email via Resend API. Returns True on success, False on failure."""
    api_key = _get_api_key()
    if api_key is None:
        logger.debug("RESEND_API_KEY not set, skipping email to %s", to_email)
        return False

    try:
        import resend

        resend.api_key = api_key
        params = {
            "from": _get_from_addr(),
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        }
        resend.Emails.send(params)  # type: ignore[arg-type]
        logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def notify_job_complete(user_email: str, job: ArchiveJob) -> bool:
    """Send a job completion notification if configured."""
    subject, html = _build_job_complete_email(job)
    return send_email(user_email, subject, html)


def notify_job_failed(user_email: str, job: ArchiveJob) -> bool:
    """Send a job failure notification if configured."""
    subject, html = _build_job_failed_email(job)
    return send_email(user_email, subject, html)
