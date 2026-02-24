"""Approval watcher — monitors Pending_Approval/ for status changes and executes actions.

Workflow (all in Obsidian):
  1. Open any file in Pending_Approval/
  2. Change `status: awaiting_approval` to one of:
     - `status: approved`  → executes the action (sends/drafts email), moves to Done/
     - `status: rejected`  → moves to Rejected/, no action taken
     - `status: revise`    → re-sends to Claude with your feedback, generates new draft
  3. For revise: optionally add a `feedback:` field in front-matter or edit the Body directly
  4. The watcher picks up the change automatically (polls every 10s)

Also still supports the legacy flow: manually move files to /Approved/ folder.
"""

import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

import config
from watchers.base_watcher import BaseWatcher

logger = logging.getLogger(__name__)


class ApprovalWatcher(BaseWatcher):
    """Watch Pending_Approval/ for status changes and /Approved/ for legacy flow."""

    name = "approval"
    check_interval = 10

    def __init__(
        self,
        output_dir: Path = config.DONE_DIR,
        check_interval: int = 10,
    ):
        super().__init__(output_dir, check_interval)
        self._linkedin = None

    def _parse_front_matter(self, text: str) -> dict:
        """Extract YAML-ish front-matter from a markdown file."""
        m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not m:
            return {}
        meta = {}
        for line in m.group(1).splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()
        return meta

    # ── Status-based approval (Obsidian-native) ──────────────────────────

    def _check_pending_approval(self) -> None:
        """Scan Pending_Approval/ for files where status has been changed."""
        if not config.PENDING_APPROVAL_DIR.exists():
            return

        for filepath in config.PENDING_APPROVAL_DIR.iterdir():
            if not filepath.is_file() or filepath.suffix != ".md":
                continue

            try:
                content = filepath.read_text(encoding="utf-8")
                meta = self._parse_front_matter(content)
                status = meta.get("status", "")

                if status == "approved":
                    logger.info("Status changed to APPROVED: %s", filepath.name)
                    self._execute_action(filepath)

                elif status == "rejected":
                    logger.info("Status changed to REJECTED: %s", filepath.name)
                    self._reject_action(filepath)

                elif status == "revise":
                    logger.info("Status changed to REVISE: %s", filepath.name)
                    self._revise_action(filepath, content, meta)

                # status: awaiting_approval — do nothing, wait for user

            except Exception:
                logger.exception("Error processing pending file: %s", filepath.name)

    # ── Execute approved action ──────────────────────────────────────────

    def _execute_action(self, filepath: Path) -> None:
        """Parse an approved file and trigger the corresponding action."""
        content = filepath.read_text(encoding="utf-8")
        meta = self._parse_front_matter(content)
        action_type = meta.get("type", "unknown")

        logger.info("Executing approved action: %s (type=%s)", filepath.name, action_type)

        success = False

        if action_type == "linkedin_post":
            success = self._execute_linkedin_post(content)

        elif action_type in ("send_email", "draft_email", "email_reply"):
            success = self._execute_email_action(action_type, meta, content)

        elif action_type == "whatsapp_reply":
            success = self._execute_whatsapp_reply(meta, content)

        else:
            logger.info("No automated handler for type '%s', marking as done", action_type)
            success = True

        # Move to Done
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = config.DONE_DIR / f"{ts}_{filepath.name}"
        shutil.move(str(filepath), str(dest))
        logger.info("Moved to Done: %s", dest.name)

        self._log_execution(filepath.name, action_type, "APPROVED", success)
        self._update_dashboard()

    # ── Reject action ────────────────────────────────────────────────────

    def _reject_action(self, filepath: Path) -> None:
        """Move rejected file to Rejected/ folder."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = config.REJECTED_DIR / f"{ts}_{filepath.name}"
        shutil.move(str(filepath), str(dest))
        logger.info("Rejected and moved: %s", dest.name)
        self._log_execution(filepath.name, "rejected", "REJECTED", True)
        self._update_dashboard()

    # ── Revise action (re-send to Claude with feedback) ──────────────────

    def _revise_action(self, filepath: Path, content: str, meta: dict) -> None:
        """Re-send to Claude with user feedback to generate a revised draft."""
        feedback = meta.get("feedback", "").strip()
        action_type = meta.get("type", "draft_email")
        to = meta.get("to", "")
        subject = meta.get("subject", "")
        task_file = meta.get("task_file", "")

        # Extract the current body
        match = re.search(r"### (?:Body|Content)\n\n(.*?)(\n---|\Z)", content, re.DOTALL)
        current_body = match.group(1).strip() if match else ""

        # Read original task for context (if it exists in Done/)
        original_context = ""
        if task_file:
            # Search Done/ for the original task
            for f in config.DONE_DIR.glob(f"*{task_file}"):
                original_context = f.read_text(encoding="utf-8")
                break

        # Build revision prompt
        import subprocess

        prompt = (
            "You are Atlas, an AI Employee assistant. The owner reviewed your draft email "
            "and wants revisions.\n\n"
            f"RECIPIENT: {to}\n"
            f"SUBJECT: {subject}\n\n"
            f"YOUR PREVIOUS DRAFT:\n{current_body}\n\n"
        )

        if feedback:
            prompt += f"OWNER'S FEEDBACK:\n{feedback}\n\n"
        else:
            prompt += (
                "The owner changed the status to 'revise' but didn't add specific feedback. "
                "They may have edited the body directly. Use the current body as the base "
                "and improve it: make it more professional, concise, and actionable.\n\n"
            )

        if original_context:
            prompt += f"ORIGINAL EMAIL CONTEXT:\n---\n{original_context}\n---\n\n"

        if action_type == "whatsapp_reply":
            prompt += (
                "Write an improved version of the draft WhatsApp reply. Rules:\n"
                "- Conversational and friendly tone (this is WhatsApp, not email)\n"
                "- Under 100 words — keep it short and direct\n"
                "- Do NOT use formal email sign-offs\n"
                "- Address the specific feedback if provided\n"
                "- Output ONLY the revised reply text, nothing else\n"
            )
        else:
            prompt += (
                "Write an improved version of the draft reply. Rules:\n"
                "- Professional and polite tone\n"
                "- Under 200 words\n"
                "- Address the specific feedback if provided\n"
                "- Output ONLY the revised email body text, nothing else\n"
            )

        logger.info("Revising draft with Claude: %s", filepath.name)

        if config.DRY_RUN:
            revised_body = f"[DRY RUN] Revised draft placeholder.\n\nOriginal: {current_body[:100]}..."
        else:
            try:
                result = subprocess.run(
                    ["claude", "--print", "-p", prompt],
                    capture_output=True, text=True, timeout=120,
                    cwd=str(config.VAULT_PATH),
                )
                revised_body = result.stdout.strip()
                if not revised_body or result.returncode != 0:
                    logger.warning("Claude revision failed, keeping original body")
                    revised_body = current_body
            except Exception:
                logger.exception("Claude revision call failed")
                revised_body = current_body

        # Rewrite the file with revised body and reset status
        unknown_banner = ""
        if "WARNING" in content:
            unknown_banner = (
                "\n> **WARNING:** This sender is not recognized. "
                "Review carefully before approving.\n"
            )

        revision_count = int(meta.get("revisions", "0")) + 1
        source = meta.get("source", "gmail")
        contact = meta.get("contact", "")

        if action_type == "whatsapp_reply":
            revised_content = (
                f"---\n"
                f"type: {action_type}\n"
                f"contact: {contact}\n"
                f"source: whatsapp\n"
                f"task_file: {task_file}\n"
                f"status: awaiting_approval\n"
                f"urgency: {meta.get('urgency', 'normal')}\n"
                f"revisions: {revision_count}\n"
                f"---\n\n"
                f"## WhatsApp Reply: {contact} (Revision {revision_count})\n\n"
                f"**To:** {contact}\n"
                f"**Reason:** Revised draft based on owner feedback\n\n"
                f"### How to act on this\n"
                f"Change `status` above to: `approved` / `rejected` / `revise`\n"
                f"To revise again, add `feedback: your instructions here` to the front-matter.\n\n"
                f"### Body\n\n"
                f"{revised_body}\n"
            )
        else:
            revised_content = (
                f"---\n"
                f"type: {action_type}\n"
                f"to: {to}\n"
                f"subject: {subject}\n"
                f"source: {source}\n"
                f"task_file: {task_file}\n"
                f"status: awaiting_approval\n"
                f"urgency: {meta.get('urgency', 'normal')}\n"
                f"revisions: {revision_count}\n"
                f"---\n\n"
                f"## Email Action: Draft Email (Revision {revision_count})\n\n"
                f"**To:** {to}\n"
                f"**Subject:** {subject}\n"
                f"**Reason:** Revised draft based on owner feedback\n"
                f"{unknown_banner}\n"
                f"### How to act on this\n"
                f"Change `status` above to: `approved` / `rejected` / `revise`\n"
                f"To revise again, add `feedback: your instructions here` to the front-matter.\n\n"
                f"### Body\n\n"
                f"{revised_body}\n"
            )

        filepath.write_text(revised_content, encoding="utf-8")
        logger.info("Revised draft saved: %s (revision %d)", filepath.name, revision_count)
        self._log_execution(filepath.name, action_type, f"REVISED (#{revision_count})", True)
        self._update_dashboard()

    # ── Email execution ──────────────────────────────────────────────────

    def _execute_linkedin_post(self, content: str) -> bool:
        """Execute a LinkedIn post action."""
        match = re.search(r"### Content\n\n(.*?)(\n---|\Z)", content, re.DOTALL)
        post_content = match.group(1).strip() if match else ""
        if post_content:
            if self._linkedin is None:
                from ai_skills.linkedin_poster import LinkedInPoster
                self._linkedin = LinkedInPoster()
            self._linkedin.publish_post(post_content)
            return True
        else:
            logger.warning("No content found in LinkedIn post file")
            return False

    def _execute_email_action(self, action_type: str, meta: dict, content: str) -> bool:
        """Execute an email action using the Gmail API directly."""
        to = meta.get("to", "")
        subject = meta.get("subject", "")

        # Extract body from content section
        match = re.search(r"### (?:Body|Content)\n\n(.*?)(\n---|\Z)", content, re.DOTALL)
        body = match.group(1).strip() if match else ""

        if not to or not body:
            logger.warning("Email action missing 'to' or body content — to=%s body_len=%d",
                           to, len(body))
            return False

        if config.DRY_RUN:
            logger.info("[DRY RUN] Would %s to=%s subject=%s", action_type, to, subject)
            return True

        from ai_skills.email_sender import send_email, draft_email

        if action_type in ("draft_email", "email_reply"):
            result = draft_email(to, subject, body)
            if result["success"]:
                logger.info("Draft created in Gmail: draft_id=%s", result.get("draft_id"))
                return True
            else:
                logger.error("Failed to create draft: %s", result.get("error"))
                return False
        elif action_type == "send_email":
            result = send_email(to, subject, body)
            if result["success"]:
                logger.info("Email sent via Gmail: message_id=%s", result.get("message_id"))
                return True
            else:
                logger.error("Failed to send email: %s", result.get("error"))
                return False
        return False

    # ── WhatsApp execution ─────────────────────────────────────────────

    def _execute_whatsapp_reply(self, meta: dict, content: str) -> bool:
        """Execute an approved WhatsApp reply."""
        contact = meta.get("contact", "")

        # Extract body from ### Body section
        match = re.search(r"### (?:Body|Content)\n\n(.*?)(\n---|\Z)", content, re.DOTALL)
        body = match.group(1).strip() if match else ""

        if not contact or not body:
            logger.warning("WhatsApp reply missing contact or body — contact=%s body_len=%d",
                           contact, len(body))
            return False

        if config.DRY_RUN:
            logger.info("[DRY RUN] Would send WhatsApp reply to=%s", contact)
            return True

        from ai_skills.whatsapp_sender import send_whatsapp_message

        result = send_whatsapp_message(contact, body)
        if result["success"]:
            logger.info("WhatsApp reply sent to=%s", contact)
            return True
        else:
            logger.error("Failed to send WhatsApp reply: %s", result.get("error"))
            return False

    # ── Logging & Dashboard ──────────────────────────────────────────────

    def _log_execution(self, filename: str, action_type: str, decision: str, success: bool) -> None:
        """Write a log entry for the action."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = config.LOGS_DIR / f"{today}.md"
        status = "OK" if success else "FAILED"
        entry = (
            f"\n- [{datetime.now().strftime('%H:%M:%S')}] "
            f"{decision}: **{filename}** (type: {action_type}) [{status}]\n"
        )
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)

    def _update_dashboard(self) -> None:
        """Update Dashboard.md counts."""
        dashboard_path = config.VAULT_PATH / "Dashboard.md"
        if not dashboard_path.exists():
            return

        pending = sum(
            1
            for d in [config.NEEDS_ACTION_DIR, config.NEEDS_ACTION_EMAIL,
                       config.NEEDS_ACTION_WHATSAPP, config.NEEDS_ACTION_LINKEDIN]
            if d.exists()
            for f in d.glob("*.md")
        )

        approval = sum(
            1 for f in config.PENDING_APPROVAL_DIR.glob("*.md")
            if f.name != ".gitkeep"
        ) if config.PENDING_APPROVAL_DIR.exists() else 0

        today_str = datetime.now().strftime("%Y%m%d")
        done_today = sum(
            1 for f in config.DONE_DIR.iterdir()
            if f.is_file() and f.name.startswith(today_str)
        ) if config.DONE_DIR.exists() else 0

        content = dashboard_path.read_text(encoding="utf-8")
        content = re.sub(r"Pending Tasks: \d+", f"Pending Tasks: {pending}", content)
        content = re.sub(r"Completed Today: \d+", f"Completed Today: {done_today}", content)
        content = re.sub(r"Needs My Approval: \d+", f"Needs My Approval: {approval}", content)
        content = re.sub(
            r"Last Updated: \d{4}-\d{2}-\d{2}",
            f"Last Updated: {datetime.now().strftime('%Y-%m-%d')}",
            content,
        )
        dashboard_path.write_text(content, encoding="utf-8")
        logger.info("Dashboard updated")

    # ── Main poll loop ───────────────────────────────────────────────────

    def check_for_updates(self) -> list[dict]:
        """Check for status changes in Pending_Approval/ and legacy Approved/ folder."""

        # Primary: check Pending_Approval/ for status changes (Obsidian-native flow)
        self._check_pending_approval()

        # Legacy: check Approved/ folder for manually moved files
        if config.APPROVED_DIR.exists():
            for filepath in config.APPROVED_DIR.iterdir():
                if filepath.is_file() and filepath.suffix == ".md":
                    try:
                        self._execute_action(filepath)
                    except Exception:
                        logger.exception("Error executing approved file: %s", filepath.name)

        return []
