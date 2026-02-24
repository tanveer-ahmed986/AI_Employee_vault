"""Unified watcher manager — runs all watchers as daemon threads with auto-restart."""

import logging
import sys
import threading
import time

import config
from watchers.inbox_watcher import InboxWatcher
from watchers.gmail_watcher import GmailWatcher
from approval_watcher import ApprovalWatcher
from scheduler import start_scheduler
from mcp_manager import get_manager as get_mcp_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOGS_DIR / "orchestrator.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("orchestrator")


def _run_with_restart(watcher_cls, *args, **kwargs):
    """Instantiate and run a watcher; restart on crash after a cooldown."""
    while True:
        try:
            watcher = watcher_cls(*args, **kwargs)
            logger.info("Starting %s watcher", watcher.name)
            watcher.run_loop()
        except Exception:
            logger.exception("Watcher %s crashed, restarting in 30s", watcher_cls.__name__)
            time.sleep(30)


# Map watcher names to their classes. LinkedIn and WhatsApp are imported
# lazily so missing dependencies (e.g. playwright) don't crash the process
# when those watchers are disabled.
WATCHER_REGISTRY: dict[str, type] = {
    "inbox": InboxWatcher,
    "gmail": GmailWatcher,
    "approval": ApprovalWatcher,
}


def _load_optional_watchers():
    """Import optional watchers only when enabled."""
    enabled = config.ENABLED_WATCHERS
    if "linkedin" in enabled:
        try:
            from watchers.linkedin_watcher import LinkedInWatcher
            WATCHER_REGISTRY["linkedin"] = LinkedInWatcher
        except ImportError:
            logger.warning("LinkedIn watcher enabled but import failed — skipping")
    if "whatsapp" in enabled:
        try:
            from watchers.whatsapp_watcher import WhatsAppWatcher
            WATCHER_REGISTRY["whatsapp"] = WhatsAppWatcher
        except ImportError:
            logger.warning("WhatsApp watcher enabled but import failed (playwright?) — skipping")


def main():
    logger.info("=" * 50)
    logger.info("  AI Employee Orchestrator — Silver Tier (Phase 1: Gmail)")
    logger.info("  DRY_RUN=%s  ENABLED_WATCHERS=%s", config.DRY_RUN, config.ENABLED_WATCHERS)
    logger.info("=" * 50)

    _load_optional_watchers()

    # Initialize MCP manager (loads server registry, starts idle reaper on demand)
    mcp = get_mcp_manager()
    logger.info("MCP Manager initialized — registered servers: %s", mcp.list_registered())

    threads: list[threading.Thread] = []
    for name in config.ENABLED_WATCHERS:
        cls = WATCHER_REGISTRY.get(name)
        if cls is None:
            logger.warning("Unknown watcher '%s' in ENABLED_WATCHERS — skipping", name)
            continue
        t = threading.Thread(target=_run_with_restart, args=(cls,), daemon=True)
        t.name = f"watcher-{cls.__name__}"
        t.start()
        threads.append(t)
        logger.info("Launched thread: %s", t.name)

    # Start the scheduler on its own daemon thread
    sched_thread = threading.Thread(target=start_scheduler, daemon=True, name="scheduler")
    sched_thread.start()
    logger.info("Launched thread: scheduler")

    # Generate today's briefing if it doesn't exist yet (covers late starts)
    from scheduler import daily_briefing
    today_str = __import__("datetime").datetime.now().strftime("%Y%m%d")
    briefing_path = config.BRIEFINGS_DIR / f"briefing_{today_str}.md"
    if not briefing_path.exists():
        logger.info("No briefing for today — generating startup briefing")
        try:
            daily_briefing()
        except Exception:
            logger.exception("Failed to generate startup briefing")
    else:
        logger.info("Today's briefing already exists: %s", briefing_path.name)

    logger.info("All watchers and scheduler running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Orchestrator shutting down — stopping MCP servers...")
        mcp.stop_all()
        logger.info("Orchestrator stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
