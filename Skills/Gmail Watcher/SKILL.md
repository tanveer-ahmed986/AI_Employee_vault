# Skill: Gmail Watcher

## Description
Monitors Gmail for unread important emails and creates action files in `/Needs_Action/Email/`.

## Trigger
- Runs automatically via the orchestrator every 60 seconds (configurable via `GMAIL_CHECK_INTERVAL`)
- Can also be invoked manually: `uv run python -c "from watchers.gmail_watcher import GmailWatcher; w = GmailWatcher(); print(w.check_for_updates())"`

## Prerequisites
1. Google Cloud project with Gmail API enabled
2. OAuth credentials downloaded to `Secrets/credentials.json`
3. First run requires browser-based OAuth consent (creates `Secrets/token.json`)

## What It Does
1. Authenticates with Gmail API using stored OAuth tokens
2. Queries for `is:unread is:important` emails (max 10 per cycle)
3. For each new email, extracts: Subject, From, Snippet, Message ID
4. Creates an action `.md` file in `Needs_Action/Email/` with metadata
5. Tracks seen message IDs to avoid duplicates

## Configuration
| Env Variable | Default | Description |
|---|---|---|
| `GMAIL_CREDENTIALS_FILE` | `Secrets/credentials.json` | Path to OAuth credentials |
| `GMAIL_TOKEN_FILE` | `Secrets/token.json` | Path to stored token |
| `GMAIL_CHECK_INTERVAL` | `60` | Seconds between checks |
| `DRY_RUN` | `true` | Skip actual API calls when true |

## Output
Action files in `Needs_Action/Email/` with format:
```
YYYYMMDD_HHMMSS_Email_Subject_Here.md
```
