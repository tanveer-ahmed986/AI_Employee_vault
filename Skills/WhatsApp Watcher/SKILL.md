# Skill: WhatsApp Watcher

## Description
Monitors WhatsApp Web for keyword-matched unread messages using Playwright and creates action files in `/Needs_Action/WhatsApp/`.

## Trigger
- Runs automatically via the orchestrator every 30 seconds (configurable via `WHATSAPP_CHECK_INTERVAL`)

## Prerequisites
1. Playwright with Chromium installed: `uv run playwright install chromium`
2. First run requires manual QR code scan (browser data persists after)

## What It Does
1. Launches a persistent Chromium browser context pointed at WhatsApp Web
2. Scans for unread chat badges
3. Opens each unread chat and reads recent messages
4. Filters messages against configured keywords (urgent, invoice, payment, action)
5. Creates action files for keyword-matched messages with contact name and content

## Configuration
| Env Variable | Default | Description |
|---|---|---|
| `WHATSAPP_KEYWORDS` | `urgent,invoice,payment,action` | Comma-separated trigger keywords |
| `WHATSAPP_CHECK_INTERVAL` | `30` | Seconds between checks |
| `WHATSAPP_USER_DATA_DIR` | `Secrets/whatsapp_browser_data` | Persistent browser profile path |
| `DRY_RUN` | `true` | Skip actual checks when true |

## Output
Action files in `Needs_Action/WhatsApp/` with format:
```
YYYYMMDD_HHMMSS_WhatsApp_ContactName.md
```
