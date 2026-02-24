"""Watcher modules for monitoring external sources."""

from watchers.gmail_watcher import GmailWatcher
from watchers.whatsapp_watcher import WhatsAppWatcher
from watchers.linkedin_watcher import LinkedInWatcher
from watchers.inbox_watcher import InboxWatcher

__all__ = ["GmailWatcher", "WhatsAppWatcher", "LinkedInWatcher", "InboxWatcher"]
