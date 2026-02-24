"""Inbox watcher — monitors /Inbox for new files, moves them to /Needs_Action with metadata."""

import logging
import shutil
from datetime import datetime
from pathlib import Path

import config
from watchers.base_watcher import BaseWatcher

logger = logging.getLogger(__name__)

EXTENSION_ACTIONS = {
    ".md":   ["Review document", "Summarize content", "Extract action items"],
    ".txt":  ["Review document", "Summarize content"],
    ".csv":  ["Analyze data", "Generate report"],
    ".pdf":  ["Review document", "Extract key information"],
    ".json": ["Parse and validate", "Review structure"],
    ".png":  ["Review image", "Add description"],
    ".jpg":  ["Review image", "Add description"],
    ".docx": ["Review document", "Summarize content", "Extract action items"],
}
DEFAULT_ACTIONS = ["Review file", "Determine next steps"]


class InboxWatcher(BaseWatcher):
    """Watch /Inbox for new files and move them to /Needs_Action with metadata."""

    name = "inbox"
    check_interval = 5

    def __init__(self, output_dir: Path = config.NEEDS_ACTION_DIR, check_interval: int = 5):
        super().__init__(output_dir, check_interval)
        self._seen: set[str] = set()
        # Snapshot existing files so we only react to new arrivals
        if config.INBOX_DIR.exists():
            for f in config.INBOX_DIR.iterdir():
                if f.is_file():
                    self._seen.add(f.name)

    def _build_metadata(self, original_name: str, timestamped_name: str, now: datetime) -> str:
        ext = Path(original_name).suffix
        actions = EXTENSION_ACTIONS.get(ext.lower(), DEFAULT_ACTIONS)
        action_lines = "\n".join(f"  - {a}" for a in actions)
        return (
            f"---\n"
            f"source_file: {original_name}\n"
            f"moved_file: {timestamped_name}\n"
            f"detected_at: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"type: auto-ingested\n"
            f"priority: normal\n"
            f"status: pending\n"
            f"---\n\n"
            f"## Auto-Ingested File\n\n"
            f"**Original filename:** {original_name}\n"
            f"**Detected:** {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"## Suggested Actions\n\n"
            f"{action_lines}\n"
        )

    def _process_file(self, filepath: Path) -> None:
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        original_name = filepath.name
        timestamped_name = f"{timestamp}_{original_name}"

        dest = config.NEEDS_ACTION_DIR / timestamped_name
        meta_dest = config.NEEDS_ACTION_DIR / f"{timestamped_name}.meta.md"

        # Handle name collisions
        counter = 1
        while dest.exists() or meta_dest.exists():
            timestamped_name = f"{timestamp}_{counter}_{original_name}"
            dest = config.NEEDS_ACTION_DIR / timestamped_name
            meta_dest = config.NEEDS_ACTION_DIR / f"{timestamped_name}.meta.md"
            counter += 1

        shutil.move(str(filepath), str(dest))
        meta_dest.write_text(
            self._build_metadata(original_name, timestamped_name, now),
            encoding="utf-8",
        )
        logger.info("Inbox: %s -> Needs_Action/%s", original_name, timestamped_name)

    def check_for_updates(self) -> list[dict]:
        """Scan /Inbox for new files and move them to /Needs_Action."""
        if not config.INBOX_DIR.exists():
            return []

        for entry in config.INBOX_DIR.iterdir():
            if not entry.is_file():
                continue
            if entry.name in self._seen:
                continue

            self._seen.add(entry.name)
            try:
                self._process_file(entry)
            except PermissionError:
                logger.warning("Permission denied: %s (may still be writing, will retry)", entry.name)
                self._seen.discard(entry.name)
            except OSError as e:
                logger.warning("OS error processing %s: %s", entry.name, e)
                self._seen.discard(entry.name)

        return []
