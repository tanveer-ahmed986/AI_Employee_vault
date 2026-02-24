"""Abstract base class for all watchers."""

import abc
import logging
import time
from datetime import datetime
from pathlib import Path


class BaseWatcher(abc.ABC):
    """Base class every watcher must inherit from."""

    name: str = "base"
    check_interval: int = 60  # seconds

    def __init__(self, output_dir: Path, check_interval: int | None = None):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if check_interval is not None:
            self.check_interval = check_interval
        self.logger = logging.getLogger(f"watcher.{self.name}")

    # ── Abstract interface ───────────────────────────────────────────────
    @abc.abstractmethod
    def check_for_updates(self) -> list[dict]:
        """Return a list of dicts, each representing one actionable item.

        Each dict should contain at least:
            - title: str
            - body: str
            - source: str  (e.g. "gmail", "whatsapp", "linkedin")
        """
        ...

    # ── Helpers ──────────────────────────────────────────────────────────
    def create_action_file(self, item: dict) -> Path:
        """Write an action .md file into self.output_dir and return its path."""
        now = datetime.now()
        ts = now.strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in item.get("title", "untitled"))
        safe_title = safe_title.strip().replace(" ", "_")[:60]
        filename = f"{ts}_{safe_title}.md"
        path = self.output_dir / filename

        body = (
            f"---\n"
            f"source: {item.get('source', self.name)}\n"
            f"detected_at: {now.isoformat()}\n"
            f"priority: {item.get('priority', 'normal')}\n"
            f"status: pending\n"
            f"---\n\n"
            f"## {item.get('title', 'Untitled')}\n\n"
            f"{item.get('body', '')}\n"
        )
        path.write_text(body, encoding="utf-8")
        self.logger.info("Created action file: %s", path.name)
        return path

    def run_loop(self) -> None:
        """Poll indefinitely at self.check_interval."""
        self.logger.info("%s watcher starting (interval=%ds)", self.name, self.check_interval)
        while True:
            try:
                items = self.check_for_updates()
                for item in items:
                    self.create_action_file(item)
            except Exception:
                self.logger.exception("Error in %s watcher loop", self.name)
            time.sleep(self.check_interval)
