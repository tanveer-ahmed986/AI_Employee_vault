"""LinkedIn watcher — monitors notifications and messages via the LinkedIn API."""

import logging
from pathlib import Path

import requests

import config
from watchers.base_watcher import BaseWatcher

logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"


class LinkedInWatcher(BaseWatcher):
    name = "linkedin"

    def __init__(
        self,
        output_dir: Path = config.NEEDS_ACTION_LINKEDIN,
        check_interval: int = config.LINKEDIN_CHECK_INTERVAL,
    ):
        super().__init__(output_dir, check_interval)
        self._seen_ids: set[str] = set()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {config.LINKEDIN_ACCESS_TOKEN}",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def _fetch_notifications(self) -> list[dict]:
        """Fetch recent LinkedIn notifications."""
        url = f"{LINKEDIN_API_BASE}/socialActions"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            return resp.json().get("elements", [])
        except requests.RequestException as e:
            logger.warning("LinkedIn notifications fetch failed: %s", e)
            return []

    def _fetch_messages(self) -> list[dict]:
        """Fetch recent LinkedIn messages (Messaging API)."""
        url = f"{LINKEDIN_API_BASE}/conversations"
        params = {"q": "search", "count": 10}
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
            resp.raise_for_status()
            return resp.json().get("elements", [])
        except requests.RequestException as e:
            logger.warning("LinkedIn messages fetch failed: %s", e)
            return []

    def check_for_updates(self) -> list[dict]:
        if config.DRY_RUN:
            self.logger.debug("DRY_RUN: skipping LinkedIn check")
            return []

        if not config.LINKEDIN_ACCESS_TOKEN:
            self.logger.warning("LINKEDIN_ACCESS_TOKEN not set, skipping")
            return []

        items: list[dict] = []

        # Check notifications
        for notif in self._fetch_notifications():
            nid = str(notif.get("id", ""))
            if not nid or nid in self._seen_ids:
                continue
            self._seen_ids.add(nid)
            items.append({
                "title": f"LinkedIn Notification: {notif.get('type', 'unknown')}",
                "body": f"**Type:** {notif.get('type')}\n**Details:** {notif}\n",
                "source": "linkedin",
                "priority": "normal",
            })

        # Check messages
        for conv in self._fetch_messages():
            cid = str(conv.get("id", ""))
            if not cid or cid in self._seen_ids:
                continue
            self._seen_ids.add(cid)

            last_msg = conv.get("lastMessage", {})
            sender = last_msg.get("from", {}).get("member", "unknown")
            text = last_msg.get("body", {}).get("text", "")

            items.append({
                "title": f"LinkedIn Message from {sender}",
                "body": (
                    f"**From:** {sender}\n"
                    f"**Message:** {text}\n"
                    f"**Conversation ID:** {cid}\n"
                ),
                "source": "linkedin",
                "priority": "normal",
            })

        if items:
            self.logger.info("Found %d new LinkedIn item(s)", len(items))
        return items
