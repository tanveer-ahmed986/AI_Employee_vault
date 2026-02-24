"""Gmail watcher — monitors unread important emails via the Gmail API."""

import json
import logging
import re
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config
from watchers.base_watcher import BaseWatcher

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]

logger = logging.getLogger(__name__)

# Gmail query: unread, in primary category (skip promotions/social/updates/forums)
GMAIL_QUERY = "is:unread category:primary"

# Sender patterns to skip — these never need a reply
_SKIP_SENDER_PATTERNS = re.compile(
    r"noreply|no-reply|no\.reply|donotreply|do-not-reply|"
    r"mailer-daemon|postmaster|notifications?@|alerts?@|"
    r"newsletter|updates@|support@.*\.noreply|accounts@|"
    r"@github\.com|@ollama\.com|@notion\.so|@deeplearning\.ai|"
    r"@medium\.com|@linkedin\.com|@vercel\.com|@netlify\.com|"
    r"@cloudflare\.com|@heroku\.com|@docker\.com|"
    r"@stackoverflow\.com|@hackerrank\.com|@udemy\.com|"
    r"@coursera\.org|security@|billing@|info@|"
    r"digest@|weekly@|daily@|automated@|system@|"
    r"@piaic\.org|@googlegroups\.com",
    re.IGNORECASE,
)

# Regex to extract raw email address from "Display Name <email@example.com>" format
_EMAIL_EXTRACT_RE = re.compile(r"<([^>]+)>")



def _get_gmail_service():
    """Authenticate and return a Gmail API service object."""
    creds = None
    token_path = Path(config.GMAIL_TOKEN_FILE)
    creds_path = Path(config.GMAIL_CREDENTIALS_FILE)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                raise FileNotFoundError(
                    f"Gmail credentials file not found at {creds_path}. "
                    "Download it from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


class GmailWatcher(BaseWatcher):
    name = "gmail"

    _SEEN_IDS_FILE = Path(config.VAULT_PATH) / "Config" / "gmail_seen_ids.json"

    def __init__(
        self,
        output_dir: Path = config.NEEDS_ACTION_EMAIL,
        check_interval: int = config.GMAIL_CHECK_INTERVAL,
    ):
        super().__init__(output_dir, check_interval)
        self._service = None
        self._seen_ids: set[str] = self._load_seen_ids()

    def _load_seen_ids(self) -> set[str]:
        """Load previously seen Gmail message IDs from disk."""
        if self._SEEN_IDS_FILE.exists():
            try:
                data = json.loads(self._SEEN_IDS_FILE.read_text(encoding="utf-8"))
                return set(data)
            except (json.JSONDecodeError, TypeError):
                pass
        return set()

    def _save_seen_ids(self) -> None:
        """Persist seen IDs to disk so restarts don't reprocess emails."""
        # Keep only the most recent 500 IDs to prevent unbounded growth
        ids_list = list(self._seen_ids)
        if len(ids_list) > 500:
            ids_list = ids_list[-500:]
            self._seen_ids = set(ids_list)
        self._SEEN_IDS_FILE.write_text(json.dumps(ids_list), encoding="utf-8")

    def _ensure_service(self):
        if self._service is None:
            self._service = _get_gmail_service()

    def check_for_updates(self) -> list[dict]:
        if config.DRY_RUN:
            self.logger.debug("DRY_RUN: skipping Gmail check")
            return []

        self._ensure_service()
        results = (
            self._service.users()
            .messages()
            .list(userId="me", q=GMAIL_QUERY, maxResults=10)
            .execute()
        )
        messages = results.get("messages", [])
        items: list[dict] = []

        for msg_stub in messages:
            msg_id = msg_stub["id"]
            if msg_id in self._seen_ids:
                continue
            self._seen_ids.add(msg_id)

            msg = (
                self._service.users()
                .messages()
                .get(userId="me", id=msg_id, format="metadata", metadataHeaders=["Subject", "From"])
                .execute()
            )
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            subject = headers.get("Subject", "(no subject)")
            sender = headers.get("From", "unknown")
            snippet = msg.get("snippet", "")

            # Skip no-reply / automated senders
            if _SKIP_SENDER_PATTERNS.search(sender):
                self.logger.debug("Skipping non-actionable email from: %s", sender)
                continue

            # Extract raw email address from "Display Name <email>" format
            email_match = _EMAIL_EXTRACT_RE.search(sender)
            sender_email = email_match.group(1) if email_match else sender

            items.append({
                "title": f"Email: {subject}",
                "body": (
                    f"**From:** {sender}\n"
                    f"**Sender Email:** {sender_email}\n"
                    f"**Subject:** {subject}\n"
                    f"**Snippet:** {snippet}\n\n"
                    f"**Gmail Message ID:** {msg_id}\n"
                ),
                "source": "gmail",
                "sender_email": sender_email,
                "priority": "normal",
            })

        if items:
            self.logger.info("Found %d new important email(s)", len(items))
        # Persist seen IDs after every check (even if no new items, we added skipped IDs)
        if messages:
            self._save_seen_ids()
        return items
