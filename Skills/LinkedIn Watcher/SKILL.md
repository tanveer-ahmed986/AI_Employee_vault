# Skill: LinkedIn Watcher

## Description
Monitors LinkedIn for new notifications and messages via the LinkedIn API and creates action files in `/Needs_Action/LinkedIn/`.

## Trigger
- Runs automatically via the orchestrator every 300 seconds (configurable via `LINKEDIN_CHECK_INTERVAL`)

## Prerequisites
1. LinkedIn Developer App with `r_liteprofile`, `r_emailaddress`, `w_member_social` scopes
2. Valid access token set in `.env` as `LINKEDIN_ACCESS_TOKEN`
3. Person URN set in `.env` as `LINKEDIN_PERSON_URN`

## What It Does
1. Authenticates with LinkedIn REST API v2
2. Checks for new social action notifications
3. Checks for new messages/conversations
4. Creates action files for each new item with sender info and content

## Configuration
| Env Variable | Default | Description |
|---|---|---|
| `LINKEDIN_ACCESS_TOKEN` | (empty) | OAuth2 access token |
| `LINKEDIN_PERSON_URN` | (empty) | Your LinkedIn person URN |
| `LINKEDIN_CHECK_INTERVAL` | `300` | Seconds between checks |
| `DRY_RUN` | `true` | Skip actual API calls when true |

## Output
Action files in `Needs_Action/LinkedIn/` with format:
```
YYYYMMDD_HHMMSS_LinkedIn_Notification_type.md
YYYYMMDD_HHMMSS_LinkedIn_Message_from_sender.md
```
