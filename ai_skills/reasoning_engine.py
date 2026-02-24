"""Reasoning engine — scans Needs_Action, classifies emails, routes to approval or Done."""

import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)

# ── Local email classification: ONLY truly junk/automated emails ─────────
# These are emails that NEVER need any human attention at all.
# Keep this VERY tight — when in doubt, let Claude decide.
_JUNK_SUBJECT_PATTERNS = re.compile(
    r"^Your OTP\b|one.time.pass(word|code)|"
    r"^Verify your email|^Confirm your email|^Email verification\b|"
    r"^Your [\w\s]+ signup code|^Your [\w\s]+ verification code|"
    r"^Password reset\b|^Reset your password\b|"
    r"^Your [\w\s]+ code is \d+",
    re.IGNORECASE,
)

# NOTE: Do NOT put broad patterns like "noreply@" here.
# Many services (Google AdSense, GitHub, etc.) use noreply addresses
# but send emails that require action. Let Claude handle those.
_JUNK_SENDER_PATTERNS = re.compile(
    r"@ollama\.com$",
    re.IGNORECASE,
)

# ── Local WhatsApp classification: skip obvious bot/spam messages ─────────
_WHATSAPP_SPAM_PATTERNS = re.compile(
    r"^this message was deleted$|"
    r"^waiting for this message|"
    r"^you were added$|"
    r"^.{0,5}joined using this group",
    re.IGNORECASE,
)

# JSON extraction from Claude response
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_RAW_JSON_RE = re.compile(r"(\{[^{}]*\"classification\"[^{}]*\})", re.DOTALL)


class ReasoningEngine:
    """Scan Needs_Action for .md files, classify, reason with Claude, and route results."""

    def __init__(self):
        self.dry_run = config.DRY_RUN

    # ── Claude CLI interface ─────────────────────────────────────────────

    def _call_claude(self, prompt: str) -> str:
        """Invoke Claude Code CLI and return its text output."""
        try:
            result = subprocess.run(
                ["claude", "--print", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(config.VAULT_PATH),
            )
            if result.returncode != 0:
                logger.warning("Claude CLI returned code %d: %s", result.returncode, result.stderr[:500])
            return result.stdout.strip()
        except FileNotFoundError:
            logger.error("'claude' CLI not found on PATH")
            return '[ERROR] Claude CLI not found'
        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timed out")
            return '[ERROR] Claude CLI timed out'

    # ── Front-matter parsing ─────────────────────────────────────────────

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

    # ── Logging helpers ──────────────────────────────────────────────────

    def _log_action(self, action: dict) -> None:
        """Append a JSON log entry to today's JSONL log file."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = config.LOGS_DIR / f"{today}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(action, default=str) + "\n")

    def _append_markdown_log(self, message: str) -> None:
        """Append a timestamped line to today's markdown log."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = config.LOGS_DIR / f"{today}.md"
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n- [{timestamp}] {message}\n")

    # ── Dashboard updater ────────────────────────────────────────────────

    def _update_dashboard(self) -> None:
        """Recount folders and update Quick Status numbers in Dashboard.md."""
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

        approval = sum(1 for f in config.PENDING_APPROVAL_DIR.glob("*.md")) if config.PENDING_APPROVAL_DIR.exists() else 0

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
        logger.info("Dashboard updated: pending=%d, approval=%d, done_today=%d", pending, approval, done_today)

    # ── Email classification (local, no Claude call) ─────────────────────

    def _classify_email(self, content: str) -> str | None:
        """Classify email as junk ONLY for truly automated/throwaway emails.

        Returns a reason string if junk, None if it needs Claude reasoning.
        Only OTPs, verification codes, and specific known-junk senders are junk.
        Everything else goes to Claude for intelligent classification.
        KEEP THIS TIGHT — better to send to Claude than to miss an important email.
        """
        subject = ""
        sender = ""
        for line in content.splitlines():
            if line.startswith("**Subject:**"):
                subject = line.replace("**Subject:**", "").strip()
            elif line.startswith("**Sender Email:**"):
                sender = line.split(":**", 1)[-1].strip()
            elif not sender and line.startswith("**From:**"):
                from_val = line.replace("**From:**", "").strip()
                m = re.search(r"<([^>]+)>", from_val)
                sender = m.group(1) if m else from_val

        # Only auto-junk if subject matches strict OTP/verification patterns
        if subject and _JUNK_SUBJECT_PATTERNS.search(subject):
            return f"Auto-classified as junk (subject: {subject[:60]})"

        # Only auto-junk for noreply/donotreply senders
        if sender and _JUNK_SENDER_PATTERNS.search(sender):
            return f"Auto-classified as junk (sender: {sender[:60]})"

        # Check snippet for OTP codes specifically
        snippet = ""
        for line in content.splitlines():
            if line.startswith("**Snippet:**"):
                snippet = line.replace("**Snippet:**", "").strip()
                break
        if snippet and re.search(r"\b\d{4,6}\b\s*(?:is your|code|otp)", snippet, re.IGNORECASE):
            return "Auto-classified as junk (OTP code in snippet)"

        return None  # Not junk — needs Claude reasoning

    # ── Claude response parsing ──────────────────────────────────────────

    def _parse_claude_email_response(self, raw: str) -> dict | None:
        """Extract structured JSON from Claude's email analysis response."""
        # Try fenced JSON block first
        m = _JSON_BLOCK_RE.search(raw)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # Try raw JSON object
        m = _RAW_JSON_RE.search(raw)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # Fallback: try to parse the whole response
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        logger.warning("Could not parse Claude email response as JSON")
        return None

    # ── Email helpers ────────────────────────────────────────────────────

    def _extract_sender_email(self, content: str) -> str:
        """Extract sender email from task file content."""
        for line in content.splitlines():
            if line.startswith("**Sender Email:**"):
                return line.replace("**Sender Email:**", "").strip()
        for line in content.splitlines():
            if line.startswith("**From:**"):
                from_val = line.replace("**From:**", "").strip()
                m = re.search(r"<([^>]+)>", from_val)
                return m.group(1) if m else from_val
        return "unknown@unknown.com"

    def _extract_subject(self, content: str) -> str:
        """Extract subject from task file content."""
        for line in content.splitlines():
            if line.startswith("**Subject:**"):
                return line.replace("**Subject:**", "").strip()
        return "(no subject)"

    # ── Create approval file ─────────────────────────────────────────────

    def _create_approval_file(
        self,
        task_path: Path,
        reply_to: str,
        reply_subject: str,
        reply_body: str,
        reason: str,
        urgency: str = "normal",
        is_unknown: bool = False,
    ) -> Path:
        """Create a properly-formatted approval file in Pending_Approval/.

        This format is exactly what approval_watcher.py expects:
        - Front-matter with type, to, subject
        - ### Body section with the draft text
        """
        task_name = task_path.stem
        file_type = "draft_email"

        unknown_banner = ""
        if is_unknown:
            unknown_banner = (
                "\n> **WARNING:** This sender is not recognized. "
                "Review carefully before approving.\n"
            )

        approval_content = (
            f"---\n"
            f"type: {file_type}\n"
            f"to: {reply_to}\n"
            f"subject: {reply_subject}\n"
            f"source: gmail\n"
            f"task_file: {task_path.name}\n"
            f"status: awaiting_approval\n"
            f"urgency: {urgency}\n"
            f"---\n\n"
            f"## Email Action: Draft Email\n\n"
            f"**To:** {reply_to}\n"
            f"**Subject:** {reply_subject}\n"
            f"**Reason:** {reason}\n"
            f"{unknown_banner}\n"
            f"### How to act on this\n"
            f"Change `status` above to: `approved` / `rejected` / `revise`\n"
            f"To revise with feedback, add `feedback: your instructions here` to the front-matter.\n\n"
            f"### Body\n\n"
            f"{reply_body}\n"
        )

        approval_path = config.PENDING_APPROVAL_DIR / f"APPROVAL_{task_name}.md"
        approval_path.write_text(approval_content, encoding="utf-8")
        logger.info("Created approval file: %s", approval_path.name)
        return approval_path

    # ── Move task to Done ────────────────────────────────────────────────

    def _move_to_done(self, task_path: Path) -> Path:
        """Move a task file to Done/ with timestamp prefix."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = config.DONE_DIR / f"{ts}_{task_path.name}"
        if dest.exists():
            dest = config.DONE_DIR / f"{ts}_dup_{task_path.name}"
        task_path.rename(dest)
        logger.info("Moved to Done: %s", dest.name)
        return dest

    # ── Email task processing ────────────────────────────────────────────

    def _process_email_task(self, task_path: Path, content: str, meta: dict) -> Path | None:
        """Full email processing: classify -> reason with Claude -> route result.

        ROUTING RULES:
        - Junk (OTP, verification, noreply) -> Done/ (no Claude call)
        - Everything else -> Pending_Approval/ (with Claude draft or placeholder)
        - Claude errors -> Pending_Approval/ as flag_for_review
        - NEVER send real emails to Done/ without human review
        """
        task_name = task_path.stem
        sender_email = self._extract_sender_email(content)
        subject = self._extract_subject(content)

        # ── Stage A: Local junk filter (strict — only obvious junk) ──────
        junk_reason = self._classify_email(content)
        if junk_reason:
            logger.info("Junk email: %s — %s", task_name, junk_reason)
            dest = self._move_to_done(task_path)
            self._log_action({
                "timestamp": datetime.now().isoformat(),
                "action": "email_auto_archived",
                "task_file": task_path.name,
                "reason": junk_reason,
                "moved_to": dest.name,
            })
            self._append_markdown_log(f"Auto-archived junk: **{subject}** — {junk_reason}")
            self._update_dashboard()
            return None

        # ── Stage B: Claude reasoning (for all non-junk emails) ──────────
        if self.dry_run:
            # DRY_RUN: still route to Pending_Approval with a placeholder
            logger.info("[DRY RUN] Routing email to Pending_Approval: %s", task_name)
            approval_path = self._create_approval_file(
                task_path=task_path,
                reply_to=sender_email,
                reply_subject=f"Re: {subject}",
                reply_body="[DRY RUN] Claude reasoning was skipped. Please write a reply manually.",
                reason="[DRY RUN] Placeholder — Claude reasoning disabled",
                urgency="normal",
                is_unknown=True,
            )
            dest = self._move_to_done(task_path)
            self._log_action({
                "timestamp": datetime.now().isoformat(),
                "action": "email_routed_to_approval",
                "task_file": task_path.name,
                "approval_file": approval_path.name,
                "dry_run": True,
            })
            self._append_markdown_log(
                f"[DRY RUN] Email routed to approval: **{subject}** → `{approval_path.name}`"
            )
            self._update_dashboard()
            return approval_path

        # Real Claude call
        prompt = self._build_email_prompt(sender_email, subject, content)
        logger.info("Sending email to Claude for reasoning: %s", task_name)
        raw_response = self._call_claude(prompt)

        if raw_response.startswith("[ERROR]"):
            # Claude failed — still route to approval as flag_for_review
            logger.error("Claude call failed for %s: %s", task_name, raw_response)
            approval_path = self._create_approval_file(
                task_path=task_path,
                reply_to=sender_email,
                reply_subject=f"Re: {subject}",
                reply_body="[Claude was unavailable. Please review this email and write a reply manually.]",
                reason=f"Claude error: {raw_response[:100]}",
                urgency="normal",
                is_unknown=True,
            )
            dest = self._move_to_done(task_path)
            self._log_action({
                "timestamp": datetime.now().isoformat(),
                "action": "email_claude_error_flagged",
                "task_file": task_path.name,
                "approval_file": approval_path.name,
                "error": raw_response[:200],
            })
            self._append_markdown_log(
                f"Claude error, flagged for review: **{subject}** → `{approval_path.name}`"
            )
            self._update_dashboard()
            return approval_path

        # Parse Claude's JSON response
        claude_result = self._parse_claude_email_response(raw_response)
        if claude_result is None:
            # Parse failure — flag for review
            claude_result = {
                "classification": "actionable",
                "reason": "Could not parse Claude response — flagging for review",
                "action_type": "flag_for_review",
                "to": sender_email,
                "subject": f"Re: {subject}",
                "body": f"[Claude response could not be parsed. Raw response below.]\n\n{raw_response[:500]}",
                "is_unknown_sender": True,
                "urgency": "normal",
            }

        # ── Stage C: Route based on Claude's decision ────────────────────
        action_type = claude_result.get("action_type", "draft_email")
        classification = claude_result.get("classification", "actionable")

        if action_type == "archive" and classification == "informational":
            # Claude says this is informational — auto-archive to Done
            dest = self._move_to_done(task_path)
            reason = claude_result.get("reason", "Informational — no action needed")
            self._log_action({
                "timestamp": datetime.now().isoformat(),
                "action": "email_archived_by_claude",
                "task_file": task_path.name,
                "reason": reason,
                "moved_to": dest.name,
            })
            self._append_markdown_log(f"Archived (Claude): **{subject}** — {reason}")
            self._update_dashboard()
            return None

        else:
            # Actionable — create approval file
            reply_to = claude_result.get("to", sender_email)
            reply_subject = claude_result.get("subject", f"Re: {subject}")
            reply_body = claude_result.get("body", "")
            reason = claude_result.get("reason", "Requires response")
            urgency = claude_result.get("urgency", "normal")
            is_unknown = claude_result.get("is_unknown_sender", False)

            approval_path = self._create_approval_file(
                task_path=task_path,
                reply_to=reply_to,
                reply_subject=reply_subject,
                reply_body=reply_body,
                reason=reason,
                urgency=urgency,
                is_unknown=is_unknown,
            )
            dest = self._move_to_done(task_path)
            self._log_action({
                "timestamp": datetime.now().isoformat(),
                "action": "email_routed_to_approval",
                "task_file": task_path.name,
                "approval_file": approval_path.name,
                "action_type": "draft_email",
                "to": reply_to,
                "subject": reply_subject,
                "urgency": urgency,
                "is_unknown_sender": is_unknown,
            })
            self._append_markdown_log(
                f"Email → approval: **{subject}** → `{approval_path.name}` (urgency={urgency})"
            )
            self._update_dashboard()
            return approval_path

    def _build_email_prompt(self, sender_email: str, subject: str, content: str) -> str:
        """Build the Claude prompt for email analysis."""
        return (
            "You are Atlas, an AI Employee assistant. Analyze this email and decide what to do.\n\n"
            "CLASSIFICATION RULES:\n"
            "1. ONLY classify as 'informational' + 'archive' if the email is a generic "
            "mass newsletter, marketing blast, or pure product announcement that has "
            "NOTHING to do with the recipient personally (e.g. 'Ollama new model released').\n"
            "2. Classify as 'actionable' + 'draft_email' if the email:\n"
            "   - Contains a question or request directed at the recipient\n"
            "   - Is about the recipient's account, site, service, or enrollment\n"
            "   - Requires the recipient to take action (fix something, attend something, confirm something)\n"
            "   - Is a business inquiry or client message\n"
            "   - Is marked IMPORTANT or URGENT\n"
            "3. When in doubt, ALWAYS classify as 'actionable' — it's better to draft a reply "
            "that gets rejected than to miss an important email.\n\n"
            "REPLY RULES (when actionable):\n"
            "- Professional and polite tone\n"
            "- Under 200 words\n"
            "- Never share credentials, API keys, or sensitive data\n"
            "- Address the sender's specific question or request\n"
            "- If the email doesn't need a reply but needs attention, write a brief acknowledgment\n"
            "- Sign off as the email account owner (not as Atlas)\n\n"
            "EXAMPLES:\n\n"
            'Email: "Hi, I want a website for ecommerce. Can you build it for me?"\n'
            "Correct: actionable, draft_email — client inquiry, needs a reply\n\n"
            'Email: "Your AdSense site needs fixes before approval"\n'
            "Correct: actionable, draft_email — recipient's site needs attention\n\n"
            'Email: "[IMPORTANT] MIT Deep Learning 2026 starts Monday"\n'
            "Correct: actionable, draft_email — recipient is enrolled, course starts soon\n\n"
            'Email: "Qwen3-Coder-Next available in Ollama"\n'
            "Correct: informational, archive — generic product announcement, not personal\n\n"
            'Email: "Welcome to DeepLearning.AI Short Courses"\n'
            "Correct: informational, archive — generic welcome/marketing email\n\n"
            f"EMAIL TO ANALYZE:\n"
            f"From: {sender_email}\n"
            f"Subject: {subject}\n\n"
            f"Full content:\n---\n{content}\n---\n\n"
            "Respond with ONLY a valid JSON object, no other text:\n"
            "{\n"
            '  "classification": "actionable" or "informational",\n'
            '  "reason": "one-line explanation of your decision",\n'
            '  "action_type": "draft_email" or "archive",\n'
            '  "to": "the sender email address to reply to",\n'
            '  "subject": "Re: the original subject",\n'
            '  "body": "your draft reply text (empty string if archive)",\n'
            '  "is_unknown_sender": true or false,\n'
            '  "urgency": "high" or "normal" or "low"\n'
            "}\n"
        )

    # ── WhatsApp helpers ────────────────────────────────────────────────

    def _extract_whatsapp_contact(self, content: str) -> str:
        """Extract contact name from WhatsApp task file content."""
        for line in content.splitlines():
            if line.startswith("**From:**"):
                return line.replace("**From:**", "").strip()
        return "Unknown"

    def _extract_whatsapp_message(self, content: str) -> str:
        """Extract the message body from WhatsApp task file content."""
        for line in content.splitlines():
            if line.startswith("**Message:**"):
                return line.replace("**Message:**", "").strip()
        return ""

    # ── WhatsApp approval file creation ──────────────────────────────────

    def _create_whatsapp_approval_file(
        self,
        task_path: Path,
        contact: str,
        original_message: str,
        reply_body: str,
        reason: str,
        urgency: str = "normal",
    ) -> Path:
        """Create an approval file for a WhatsApp reply in Pending_Approval/."""
        task_name = task_path.stem

        approval_content = (
            f"---\n"
            f"type: whatsapp_reply\n"
            f"contact: {contact}\n"
            f"source: whatsapp\n"
            f"task_file: {task_path.name}\n"
            f"status: awaiting_approval\n"
            f"urgency: {urgency}\n"
            f"---\n\n"
            f"## WhatsApp Reply: {contact}\n\n"
            f"**To:** {contact}\n"
            f"**Original Message:** {original_message}\n"
            f"**Reason:** {reason}\n\n"
            f"### How to act on this\n"
            f"Change `status` above to: `approved` / `rejected` / `revise`\n"
            f"To revise with feedback, add `feedback: your instructions here` to the front-matter.\n\n"
            f"### Body\n\n"
            f"{reply_body}\n"
        )

        approval_path = config.PENDING_APPROVAL_DIR / f"APPROVAL_{task_name}.md"
        approval_path.write_text(approval_content, encoding="utf-8")
        logger.info("Created WhatsApp approval file: %s", approval_path.name)
        return approval_path

    # ── WhatsApp task processing ─────────────────────────────────────────

    def _process_whatsapp_task(self, task_path: Path, content: str, meta: dict) -> Path | None:
        """Full WhatsApp processing: classify -> reason with Claude -> route result.

        Mirrors _process_email_task() but with WhatsApp-specific prompts and routing.
        """
        task_name = task_path.stem
        contact = self._extract_whatsapp_contact(content)
        message_text = self._extract_whatsapp_message(content)
        urgency = meta.get("priority", "normal")

        # ── Stage A: Local spam filter ────────────────────────────────────
        if message_text and _WHATSAPP_SPAM_PATTERNS.search(message_text):
            reason = f"Auto-classified as spam (WhatsApp system message)"
            logger.info("Spam WhatsApp message: %s — %s", task_name, reason)
            dest = self._move_to_done(task_path)
            self._log_action({
                "timestamp": datetime.now().isoformat(),
                "action": "whatsapp_auto_archived",
                "task_file": task_path.name,
                "reason": reason,
                "moved_to": dest.name,
            })
            self._append_markdown_log(f"Auto-archived WhatsApp spam: **{contact}** — {reason}")
            self._update_dashboard()
            return None

        # ── Stage B: Claude reasoning ─────────────────────────────────────
        if self.dry_run:
            logger.info("[DRY RUN] Routing WhatsApp to Pending_Approval: %s", task_name)
            approval_path = self._create_whatsapp_approval_file(
                task_path=task_path,
                contact=contact,
                original_message=message_text,
                reply_body="[DRY RUN] Claude reasoning was skipped. Please write a reply manually.",
                reason="[DRY RUN] Placeholder — Claude reasoning disabled",
                urgency=urgency,
            )
            dest = self._move_to_done(task_path)
            self._log_action({
                "timestamp": datetime.now().isoformat(),
                "action": "whatsapp_routed_to_approval",
                "task_file": task_path.name,
                "approval_file": approval_path.name,
                "dry_run": True,
            })
            self._append_markdown_log(
                f"[DRY RUN] WhatsApp → approval: **{contact}** → `{approval_path.name}`"
            )
            self._update_dashboard()
            return approval_path

        # Real Claude call
        prompt = self._build_whatsapp_prompt(contact, message_text, content)
        logger.info("Sending WhatsApp task to Claude for reasoning: %s", task_name)
        raw_response = self._call_claude(prompt)

        if raw_response.startswith("[ERROR]"):
            logger.error("Claude call failed for WhatsApp %s: %s", task_name, raw_response)
            approval_path = self._create_whatsapp_approval_file(
                task_path=task_path,
                contact=contact,
                original_message=message_text,
                reply_body="[Claude was unavailable. Please review and write a reply manually.]",
                reason=f"Claude error: {raw_response[:100]}",
                urgency=urgency,
            )
            dest = self._move_to_done(task_path)
            self._log_action({
                "timestamp": datetime.now().isoformat(),
                "action": "whatsapp_claude_error_flagged",
                "task_file": task_path.name,
                "approval_file": approval_path.name,
                "error": raw_response[:200],
            })
            self._append_markdown_log(
                f"Claude error, flagged for review: WhatsApp from **{contact}** → `{approval_path.name}`"
            )
            self._update_dashboard()
            return approval_path

        # Parse Claude's JSON response
        claude_result = self._parse_claude_email_response(raw_response)
        if claude_result is None:
            claude_result = {
                "classification": "actionable",
                "reason": "Could not parse Claude response — flagging for review",
                "action_type": "reply",
                "body": f"[Claude response could not be parsed.]\n\n{raw_response[:500]}",
                "urgency": urgency,
            }

        # ── Stage C: Route based on Claude's decision ─────────────────────
        action_type = claude_result.get("action_type", "reply")
        classification = claude_result.get("classification", "actionable")

        if action_type == "ignore" and classification == "informational":
            dest = self._move_to_done(task_path)
            reason = claude_result.get("reason", "Informational — no reply needed")
            self._log_action({
                "timestamp": datetime.now().isoformat(),
                "action": "whatsapp_archived_by_claude",
                "task_file": task_path.name,
                "reason": reason,
                "moved_to": dest.name,
            })
            self._append_markdown_log(f"Archived (Claude): WhatsApp from **{contact}** — {reason}")
            self._update_dashboard()
            return None

        else:
            reply_body = claude_result.get("body", "")
            reason = claude_result.get("reason", "Requires response")
            urgency = claude_result.get("urgency", urgency)

            approval_path = self._create_whatsapp_approval_file(
                task_path=task_path,
                contact=contact,
                original_message=message_text,
                reply_body=reply_body,
                reason=reason,
                urgency=urgency,
            )
            dest = self._move_to_done(task_path)
            self._log_action({
                "timestamp": datetime.now().isoformat(),
                "action": "whatsapp_routed_to_approval",
                "task_file": task_path.name,
                "approval_file": approval_path.name,
                "contact": contact,
                "urgency": urgency,
            })
            self._append_markdown_log(
                f"WhatsApp → approval: **{contact}** → `{approval_path.name}` (urgency={urgency})"
            )
            self._update_dashboard()
            return approval_path

    def _build_whatsapp_prompt(self, contact: str, message_text: str, full_content: str) -> str:
        """Build the Claude prompt for WhatsApp message analysis."""
        return (
            "You are Atlas, an AI Employee assistant. Analyze this WhatsApp message and decide what to do.\n\n"
            "CLASSIFICATION RULES:\n"
            "1. Classify as 'informational' + 'ignore' if the message is:\n"
            "   - A generic group broadcast or forwarded chain message\n"
            "   - A simple greeting with no question (e.g. 'hi', 'hello')\n"
            "   - A system notification or bot message\n"
            "2. Classify as 'actionable' + 'reply' if the message:\n"
            "   - Contains a direct question or request\n"
            "   - Is about a project, meeting, invoice, payment, or deadline\n"
            "   - Requires acknowledgment or a response\n"
            "   - Is marked urgent or time-sensitive\n"
            "3. When in doubt, classify as 'actionable' — better to draft a reply than miss something.\n\n"
            "REPLY RULES (when actionable):\n"
            "- Conversational and friendly tone (this is WhatsApp, not email)\n"
            "- Under 100 words — keep it short and direct\n"
            "- Never share credentials, API keys, or sensitive data\n"
            "- Address the sender's specific question or request\n"
            "- Do NOT use formal email sign-offs\n\n"
            f"WHATSAPP MESSAGE TO ANALYZE:\n"
            f"From: {contact}\n"
            f"Message: {message_text}\n\n"
            f"Full task file:\n---\n{full_content}\n---\n\n"
            "Respond with ONLY a valid JSON object, no other text:\n"
            "{\n"
            '  "classification": "actionable" or "informational",\n'
            '  "reason": "one-line explanation of your decision",\n'
            '  "action_type": "reply" or "ignore",\n'
            '  "body": "your draft reply text (empty string if ignore)",\n'
            '  "urgency": "high" or "normal" or "low"\n'
            "}\n"
        )

    # ── Generic task processing (non-email) ──────────────────────────────

    def _process_generic_task(self, task_path: Path, content: str, meta: dict) -> Path | None:
        """Process non-email tasks with existing plan-based approach."""
        task_name = task_path.stem
        source = meta.get("source", "unknown")

        prompt = (
            f"You are Atlas, an AI Employee. Read the following task file and create a step-by-step plan.\n"
            f"Task file name: {task_path.name}\n\n"
            f"---\n{content}\n---\n\n"
            f"Output a plan in markdown with: Objective, Context, Steps (numbered checkboxes), "
            f"and note if any step requires human approval."
        )

        logger.info("Processing generic task: %s", task_name)

        if self.dry_run:
            plan_text = (
                f"## Plan for {task_name}\n\n"
                f"**[DRY RUN]** — Claude reasoning skipped.\n\n"
                f"### Objective\nProcess {task_name}\n\n"
                f"### Steps\n- [ ] Review task content\n- [ ] Execute actions\n- [ ] Log results\n"
            )
        else:
            plan_text = self._call_claude(prompt)

        plan_path = config.PLANS_DIR / f"PLAN_{task_name}.md"
        plan_content = (
            f"---\n"
            f"task_file: {task_path.name}\n"
            f"source: {source}\n"
            f"created_at: {datetime.now().isoformat()}\n"
            f"status: pending\n"
            f"---\n\n"
            f"{plan_text}\n"
        )
        plan_path.write_text(plan_content, encoding="utf-8")
        logger.info("Plan created: %s", plan_path.name)

        dest = self._move_to_done(task_path)

        self._log_action({
            "timestamp": datetime.now().isoformat(),
            "action": "reasoning",
            "task_file": task_path.name,
            "plan_file": plan_path.name,
            "routed_to": "Plans",
            "moved_to": dest.name,
            "dry_run": self.dry_run,
        })
        self._append_markdown_log(f"Generic task: **{task_name}** → plan `{plan_path.name}`")
        self._update_dashboard()
        return plan_path

    # ── Main entry points ────────────────────────────────────────────────

    def process_task(self, task_path: Path) -> Path | None:
        """Read a task file, classify it, and route appropriately."""
        if not task_path.exists():
            logger.warning("Task file not found: %s", task_path)
            return None

        content = task_path.read_text(encoding="utf-8")
        meta = self._parse_front_matter(content)
        source = meta.get("source", "")

        if source == "gmail":
            return self._process_email_task(task_path, content, meta)
        elif source == "whatsapp":
            return self._process_whatsapp_task(task_path, content, meta)
        else:
            return self._process_generic_task(task_path, content, meta)

    def process_all(self) -> list[Path]:
        """Process all .md files in every Needs_Action subdirectory."""
        results: list[Path] = []
        search_dirs = [
            config.NEEDS_ACTION_DIR,
            config.NEEDS_ACTION_EMAIL,
            config.NEEDS_ACTION_WHATSAPP,
            config.NEEDS_ACTION_LINKEDIN,
        ]
        for d in search_dirs:
            if not d.exists():
                continue
            for md_file in sorted(d.glob("*.md")):
                result = self.process_task(md_file)
                if result:
                    results.append(result)
        return results
