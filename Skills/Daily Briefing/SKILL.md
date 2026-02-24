# Skill: Daily Briefing

## Description
Generates a daily summary of pending tasks, items awaiting approval, and completed work. Saved to `/Briefings/`.

## Trigger
- Scheduled: daily at 8:00 AM (configurable via `BRIEFING_HOUR`)
- Manual: `uv run python -c "from scheduler import daily_briefing; daily_briefing()"`

## What It Does
1. Counts pending tasks across all `Needs_Action/` subdirectories
2. Counts items in `Pending_Approval/`
3. Counts items completed today in `Done/`
4. Generates a markdown briefing with:
   - Date and summary statistics
   - Action items checklist
5. Saves to `Briefings/briefing_YYYYMMDD.md`

## Configuration
| Env Variable    | Default | Description                          |
| --------------- | ------- | ------------------------------------ |
| `BRIEFING_HOUR` | `8`     | Hour (24h) to run the daily briefing |

## Output
Briefing files in `Briefings/` with format:
```
briefing_YYYYMMDD.md
```
