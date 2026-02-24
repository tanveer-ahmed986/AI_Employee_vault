"""WhatsApp sender — sends messages via WhatsApp Web using Playwright.

Uses a persistent Chromium browser context so WhatsApp QR login is remembered.
Follows the same return-dict pattern as email_sender.py.
"""

import logging
from pathlib import Path

from playwright.sync_api import sync_playwright

import config

logger = logging.getLogger(__name__)


def send_whatsapp_message(contact_name: str, message: str) -> dict:
    """Send a WhatsApp message to a contact via WhatsApp Web.

    Args:
        contact_name: The display name of the contact (must match WhatsApp exactly).
        message: The message text to send.

    Returns:
        dict with 'success' (bool) and 'error' (str | None).
    """
    if config.DRY_RUN:
        logger.info("[DRY RUN] Would send WhatsApp message to=%s len=%d", contact_name, len(message))
        return {"success": True, "error": None}

    if not contact_name or not message:
        return {"success": False, "error": "Missing contact_name or message"}

    user_data = Path(config.WHATSAPP_USER_DATA_DIR)
    user_data.mkdir(parents=True, exist_ok=True)

    pw = None
    try:
        pw = sync_playwright().start()
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(user_data),
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.new_page()
        page.goto("https://web.whatsapp.com", wait_until="networkidle", timeout=60_000)

        # Search for the contact
        search_box = page.wait_for_selector(
            '[contenteditable="true"][data-tab="3"]',
            timeout=30_000,
        )
        search_box.click()
        search_box.fill(contact_name)
        page.wait_for_timeout(2000)

        # Click the matching contact in search results
        contact_el = page.wait_for_selector(
            f'span[title="{contact_name}"]',
            timeout=10_000,
        )
        contact_el.click()
        page.wait_for_timeout(1000)

        # Type and send the message
        msg_box = page.wait_for_selector(
            '[contenteditable="true"][data-tab="10"]',
            timeout=10_000,
        )
        msg_box.click()
        msg_box.fill(message)
        page.wait_for_timeout(500)

        # Press Enter to send
        msg_box.press("Enter")
        page.wait_for_timeout(2000)

        logger.info("WhatsApp message sent to=%s len=%d", contact_name, len(message))
        context.close()
        return {"success": True, "error": None}

    except Exception as e:
        logger.exception("Failed to send WhatsApp message to=%s", contact_name)
        return {"success": False, "error": str(e)}
    finally:
        if pw:
            pw.stop()
