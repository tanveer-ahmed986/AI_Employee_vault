"""WhatsApp Web watcher — uses Playwright to monitor for keyword-matched messages."""

import logging
from pathlib import Path

from playwright.sync_api import sync_playwright, Browser, BrowserContext

import config
from watchers.base_watcher import BaseWatcher

logger = logging.getLogger(__name__)


class WhatsAppWatcher(BaseWatcher):
    name = "whatsapp"

    def __init__(
        self,
        output_dir: Path = config.NEEDS_ACTION_WHATSAPP,
        check_interval: int = config.WHATSAPP_CHECK_INTERVAL,
    ):
        super().__init__(output_dir, check_interval)
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page = None
        self._seen_texts: set[str] = set()

    def _ensure_browser(self):
        """Launch a persistent Chromium context so QR login is remembered."""
        if self._page is not None:
            return

        user_data = Path(config.WHATSAPP_USER_DATA_DIR)
        user_data.mkdir(parents=True, exist_ok=True)

        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data),
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._page = self._context.new_page()
        self._page.goto("https://web.whatsapp.com", wait_until="networkidle", timeout=60_000)
        logger.info("WhatsApp Web page loaded (scan QR if first run)")

    def check_for_updates(self) -> list[dict]:
        if config.DRY_RUN:
            self.logger.debug("DRY_RUN: skipping WhatsApp check")
            return []

        self._ensure_browser()
        items: list[dict] = []

        try:
            # Find unread chat badges
            unread_chats = self._page.query_selector_all('[aria-label*="unread"]')
            for chat in unread_chats[:5]:  # limit to 5 per cycle
                try:
                    chat.click()
                    self._page.wait_for_timeout(1000)

                    # Read recent messages from the open conversation
                    msg_elements = self._page.query_selector_all("div.message-in span.selectable-text")
                    for el in msg_elements[-10:]:  # last 10 messages
                        text = el.inner_text().strip()
                        if not text or text in self._seen_texts:
                            continue

                        # Check keyword match
                        text_lower = text.lower()
                        matched = any(kw in text_lower for kw in config.WHATSAPP_KEYWORDS)
                        if not matched:
                            self._seen_texts.add(text)
                            continue

                        self._seen_texts.add(text)

                        # Try to extract contact name
                        header = self._page.query_selector("header span[title]")
                        contact = header.get_attribute("title") if header else "Unknown"

                        items.append({
                            "title": f"WhatsApp: {contact}",
                            "body": (
                                f"**From:** {contact}\n"
                                f"**Message:** {text}\n"
                                f"**Keyword match:** {[kw for kw in config.WHATSAPP_KEYWORDS if kw in text_lower]}\n"
                            ),
                            "source": "whatsapp",
                            "priority": "high" if "urgent" in text_lower else "normal",
                        })
                except Exception:
                    logger.exception("Error reading WhatsApp chat")

        except Exception:
            logger.exception("Error scanning WhatsApp unread chats")

        if items:
            self.logger.info("Found %d keyword-matched WhatsApp message(s)", len(items))
        return items

    def shutdown(self):
        """Clean up browser resources."""
        if self._context:
            self._context.close()
        if self._playwright:
            self._playwright.stop()
        self._page = None
        self._context = None
        self._playwright = None
