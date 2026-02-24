"""Email sender — sends and drafts emails directly via Gmail API.

Eliminates dependency on Claude CLI or MCP server for the actual send/draft step.
Uses the same OAuth credentials as gmail_watcher.
"""

import base64
import logging
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import config

logger = logging.getLogger(__name__)

# Must match the scopes used by gmail_oauth_setup.py (what the token was created with)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]


def _get_gmail_service():
    """Authenticate and return a Gmail API service object."""
    token_path = Path(config.GMAIL_TOKEN_FILE)
    creds_path = Path(config.GMAIL_CREDENTIALS_FILE)

    if not token_path.exists():
        raise FileNotFoundError(
            f"Gmail token not found at {token_path}. "
            "Run gmail_oauth_setup.py first."
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise RuntimeError(
                "Gmail credentials expired and cannot be refreshed. "
                "Re-run gmail_oauth_setup.py."
            )

    return build("gmail", "v1", credentials=creds)


def _build_message(to: str, subject: str, body: str) -> dict:
    """Build a Gmail-compatible MIME message."""
    message = MIMEText(body, "plain", "utf-8")
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    return {"raw": raw}


def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email immediately via Gmail.

    Returns dict with 'success', 'message_id', and 'error' keys.
    """
    if config.DRY_RUN:
        logger.info("[DRY RUN] Would send email to=%s subject=%s", to, subject)
        return {"success": True, "message_id": "dry_run", "error": None}

    try:
        service = _get_gmail_service()
        raw_message = _build_message(to, subject, body)
        result = service.users().messages().send(
            userId="me", body=raw_message
        ).execute()
        msg_id = result.get("id", "unknown")
        logger.info("Email sent: to=%s subject=%s message_id=%s", to, subject, msg_id)
        return {"success": True, "message_id": msg_id, "error": None}
    except Exception as e:
        logger.exception("Failed to send email to=%s subject=%s", to, subject)
        return {"success": False, "message_id": None, "error": str(e)}


def draft_email(to: str, subject: str, body: str) -> dict:
    """Create a Gmail draft (does not send).

    Returns dict with 'success', 'draft_id', and 'error' keys.
    """
    if config.DRY_RUN:
        logger.info("[DRY RUN] Would draft email to=%s subject=%s", to, subject)
        return {"success": True, "draft_id": "dry_run", "error": None}

    try:
        service = _get_gmail_service()
        raw_message = _build_message(to, subject, body)
        result = service.users().drafts().create(
            userId="me", body={"message": raw_message}
        ).execute()
        draft_id = result.get("id", "unknown")
        logger.info("Draft created: to=%s subject=%s draft_id=%s", to, subject, draft_id)
        return {"success": True, "draft_id": draft_id, "error": None}
    except Exception as e:
        logger.exception("Failed to create draft to=%s subject=%s", to, subject)
        return {"success": False, "draft_id": None, "error": str(e)}
