# Skill Registry

All available Agent Skills for the AI Employee system.

## Watchers (Automated Input)
| Skill | Folder | Type | Schedule |
|---|---|---|---|
| Gmail Watcher | `Skills/Gmail Watcher/` | Automated | Every 60s |
| WhatsApp Watcher | `Skills/WhatsApp Watcher/` | Automated | Every 30s |
| LinkedIn Watcher | `Skills/LinkedIn Watcher/` | Automated | Every 300s |

## Skills (Processing & Output)
| Skill | Folder | Type | Schedule |
|---|---|---|---|
| Reasoning Engine | `Skills/Reasoning Engine/` | Automated | Every 5 min |
| LinkedIn Poster | `Skills/LinkedIn Poster/` | Scheduled | Weekdays 10 AM |
| Email Sender | `Skills/Email Sender/` | MCP Tool | On demand |
| Daily Briefing | `Skills/Daily Briefing/` | Scheduled | Daily 8 AM |

## Original Skills (Bronze Tier)
| Skill | Folder | Type |
|---|---|---|
| Process Task | `Skills/Process Task/` | Manual |
| Summarize File | `Skills/Summarize File/` | Manual |
| Summarize PDF | `Skills/Summarize PDF/` | Manual |

## Adding New Skills
1. Create a folder in `/Skills/` with your skill name
2. Add a `SKILL.md` file following the template in existing skills
3. Register the skill in this file
4. If it needs code, add a module in the `ai_skills/` Python package
