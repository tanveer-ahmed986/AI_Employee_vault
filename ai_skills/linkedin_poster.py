"""LinkedIn auto-poster skill — drafts posts for approval and publishes approved ones."""

import json
import logging
from datetime import datetime
from pathlib import Path

import requests

import config

logger = logging.getLogger(__name__)

LINKEDIN_UGC_URL = "https://api.linkedin.com/v2/ugcPosts"


class LinkedInPoster:
    """Create LinkedIn post drafts and publish approved posts."""

    def __init__(self):
        self.dry_run = config.DRY_RUN

    def create_post_draft(self, content: str, *, topic: str = "General") -> Path:
        """Save a post draft to Pending_Approval for human review."""
        now = datetime.now()
        ts = now.strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_linkedin_post_{topic.replace(' ', '_')[:30]}.md"
        path = config.PENDING_APPROVAL_DIR / filename

        body = (
            f"---\n"
            f"type: linkedin_post\n"
            f"topic: {topic}\n"
            f"created_at: {now.isoformat()}\n"
            f"status: pending_approval\n"
            f"---\n\n"
            f"## LinkedIn Post Draft\n\n"
            f"**Topic:** {topic}\n\n"
            f"### Content\n\n"
            f"{content}\n\n"
            f"---\n"
            f"*Move this file to /Approved to publish, or /Rejected to discard.*\n"
        )
        path.write_text(body, encoding="utf-8")
        logger.info("LinkedIn post draft saved: %s", path.name)
        return path

    def publish_post(self, content: str) -> dict:
        """Publish a post to LinkedIn via the UGC API."""
        if self.dry_run:
            logger.info("DRY_RUN: Would publish LinkedIn post (%d chars)", len(content))
            return {"dry_run": True, "content_length": len(content)}

        if not config.LINKEDIN_ACCESS_TOKEN or not config.LINKEDIN_PERSON_URN:
            raise ValueError("LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN must be set")

        payload = {
            "author": f"urn:li:person:{config.LINKEDIN_PERSON_URN}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        headers = {
            "Authorization": f"Bearer {config.LINKEDIN_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        resp = requests.post(LINKEDIN_UGC_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        logger.info("LinkedIn post published: %s", result.get("id", "unknown"))
        return result
