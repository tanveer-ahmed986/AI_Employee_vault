"""
File Watcher for AI Employee Vault
Watches /Inbox for new files, moves them to /Needs_Action with timestamps,
and creates metadata files alongside them.
"""

import os
import sys
import time
import shutil
from datetime import datetime
from pathlib import Path

VAULT_DIR = Path(__file__).parent
INBOX_DIR = VAULT_DIR / "Inbox"
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
POLL_INTERVAL = 2  # seconds

EXTENSION_ACTIONS = {
    ".md":   ["Review document", "Summarize content", "Extract action items"],
    ".txt":  ["Review document", "Summarize content"],
    ".csv":  ["Analyze data", "Generate report"],
    ".pdf":  ["Review document", "Extract key information"],
    ".json": ["Parse and validate", "Review structure"],
    ".png":  ["Review image", "Add description"],
    ".jpg":  ["Review image", "Add description"],
}
DEFAULT_ACTIONS = ["Review file", "Determine next steps"]


def get_suggested_actions(extension: str) -> list[str]:
    return EXTENSION_ACTIONS.get(extension.lower(), DEFAULT_ACTIONS)


def build_metadata(original_name: str, timestamped_name: str, now: datetime) -> str:
    ext = Path(original_name).suffix
    actions = get_suggested_actions(ext)
    action_lines = "\n".join(f"  - {a}" for a in actions)
    return (
        f"---\n"
        f"source_file: {original_name}\n"
        f"moved_file: {timestamped_name}\n"
        f"detected_at: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"type: auto-ingested\n"
        f"priority: normal\n"
        f"status: pending\n"
        f"---\n"
        f"\n"
        f"## Auto-Ingested File\n"
        f"\n"
        f"**Original filename:** {original_name}\n"
        f"**Detected:** {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"\n"
        f"## Suggested Actions\n"
        f"\n"
        f"{action_lines}\n"
    )


def process_file(filepath: Path) -> None:
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    original_name = filepath.name
    timestamped_name = f"{timestamp}_{original_name}"

    dest = NEEDS_ACTION_DIR / timestamped_name
    meta_dest = NEEDS_ACTION_DIR / f"{timestamped_name}.meta.md"

    # Handle name collisions by appending a counter
    counter = 1
    while dest.exists() or meta_dest.exists():
        timestamped_name = f"{timestamp}_{counter}_{original_name}"
        dest = NEEDS_ACTION_DIR / timestamped_name
        meta_dest = NEEDS_ACTION_DIR / f"{timestamped_name}.meta.md"
        counter += 1

    shutil.move(str(filepath), str(dest))
    meta_dest.write_text(build_metadata(original_name, timestamped_name, now), encoding="utf-8")

    print(f"[{now.strftime('%H:%M:%S')}] Detected: {original_name}")
    print(f"  -> Moved to: Needs_Action/{timestamped_name}")
    print(f"  -> Metadata: Needs_Action/{meta_dest.name}")


def watch() -> None:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("  AI Employee File Watcher")
    print(f"  Watching: {INBOX_DIR}")
    print(f"  Moving to: {NEEDS_ACTION_DIR}")
    print(f"  Poll interval: {POLL_INTERVAL}s")
    print("  Press Ctrl+C to stop")
    print("=" * 50)

    seen: set[str] = set()

    # Snapshot existing files so we only react to new arrivals
    try:
        for f in INBOX_DIR.iterdir():
            if f.is_file():
                seen.add(f.name)
    except OSError as e:
        print(f"Warning: could not read Inbox on startup: {e}")

    while True:
        try:
            for entry in INBOX_DIR.iterdir():
                if not entry.is_file():
                    continue
                if entry.name in seen:
                    continue

                seen.add(entry.name)
                try:
                    process_file(entry)
                except PermissionError:
                    print(f"  [!] Permission denied: {entry.name} (file may still be writing, will retry)")
                    seen.discard(entry.name)
                except OSError as e:
                    print(f"  [!] OS error processing {entry.name}: {e}")
                    seen.discard(entry.name)

        except OSError as e:
            print(f"  [!] Error scanning Inbox: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        watch()
    except KeyboardInterrupt:
        print("\nFile watcher stopped.")
        sys.exit(0)
