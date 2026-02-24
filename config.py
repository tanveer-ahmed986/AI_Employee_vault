"""Central configuration for the AI Employee system."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Vault paths ──────────────────────────────────────────────────────────
VAULT_PATH = Path(__file__).parent
INBOX_DIR = VAULT_PATH / "Inbox"
NEEDS_ACTION_DIR = VAULT_PATH / "Needs_Action"
NEEDS_ACTION_EMAIL = NEEDS_ACTION_DIR / "Email"
NEEDS_ACTION_WHATSAPP = NEEDS_ACTION_DIR / "WhatsApp"
NEEDS_ACTION_LINKEDIN = NEEDS_ACTION_DIR / "LinkedIn"
PLANS_DIR = VAULT_PATH / "Plans"
DONE_DIR = VAULT_PATH / "Done"
PENDING_APPROVAL_DIR = VAULT_PATH / "Pending_Approval"
APPROVED_DIR = VAULT_PATH / "Approved"
REJECTED_DIR = VAULT_PATH / "Rejected"
LOGS_DIR = VAULT_PATH / "Logs"
SKILLS_DIR = VAULT_PATH / "Skills"
BRIEFINGS_DIR = VAULT_PATH / "Briefings"
TEMPLATES_DIR = VAULT_PATH / "Templates"
CONFIG_DIR = VAULT_PATH / "Config"

# ── Ensure all directories exist ─────────────────────────────────────────
for d in [
    INBOX_DIR, NEEDS_ACTION_DIR, NEEDS_ACTION_EMAIL, NEEDS_ACTION_WHATSAPP,
    NEEDS_ACTION_LINKEDIN, PLANS_DIR, DONE_DIR, PENDING_APPROVAL_DIR,
    APPROVED_DIR, REJECTED_DIR, LOGS_DIR, SKILLS_DIR, BRIEFINGS_DIR,
    TEMPLATES_DIR, CONFIG_DIR,
]:
    d.mkdir(parents=True, exist_ok=True)

# ── Feature flags ────────────────────────────────────────────────────────
DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")
ENABLED_WATCHERS = [
    w.strip()
    for w in os.getenv("ENABLED_WATCHERS", "inbox,gmail,approval").split(",")
    if w.strip()
]

# ── Gmail credentials ────────────────────────────────────────────────────
GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_PATH", os.getenv("GMAIL_CREDENTIALS_FILE", str(VAULT_PATH / "Secrets" / "credentials.json")))
GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", str(VAULT_PATH / "Secrets" / "token.json"))
GMAIL_CHECK_INTERVAL = int(os.getenv("GMAIL_CHECK_INTERVAL", "60"))

# ── LinkedIn credentials ─────────────────────────────────────────────────
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN = os.getenv("LINKEDIN_PERSON_URN", "")
LINKEDIN_CHECK_INTERVAL = int(os.getenv("LINKEDIN_CHECK_INTERVAL", "300"))

# ── WhatsApp settings ────────────────────────────────────────────────────
WHATSAPP_KEYWORDS = [
    kw.strip()
    for kw in os.getenv("WHATSAPP_KEYWORDS", "urgent,invoice,payment,action").split(",")
    if kw.strip()
]
WHATSAPP_CHECK_INTERVAL = int(os.getenv("WHATSAPP_CHECK_INTERVAL", "30"))
WHATSAPP_USER_DATA_DIR = os.getenv(
    "WHATSAPP_USER_DATA_DIR",
    str(VAULT_PATH / "Secrets" / "whatsapp_browser_data"),
)

# ── Scheduling ───────────────────────────────────────────────────────────
BRIEFING_HOUR = int(os.getenv("BRIEFING_HOUR", "8"))
LINKEDIN_POST_HOUR = int(os.getenv("LINKEDIN_POST_HOUR", "10"))
PROCESSING_INTERVAL_MIN = int(os.getenv("PROCESSING_INTERVAL_MIN", "5"))
