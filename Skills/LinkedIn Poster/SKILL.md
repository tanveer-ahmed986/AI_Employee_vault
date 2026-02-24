# Skill: LinkedIn Poster

## Description
Creates LinkedIn post drafts for human approval and publishes approved posts via the LinkedIn UGC API.

## Trigger
- Scheduled: weekdays at 10:00 AM (configurable via `LINKEDIN_POST_HOUR`)
- Manual: can be invoked from the reasoning engine

## Prerequisites
1. LinkedIn Developer App with `w_member_social` scope
2. `LINKEDIN_ACCESS_TOKEN` and `LINKEDIN_PERSON_URN` set in `.env`

## Workflow
1. **Draft Generation**: Claude generates a professional LinkedIn post
2. **Approval**: Draft saved to `/Pending_Approval/` as a markdown file
3. **Human Review**: User moves file to `/Approved/` or `/Rejected/`
4. **Publication**: Approval watcher detects the file and publishes via LinkedIn API

## Company Handbook Rules
- Posts must be professional and business-focused
- No personal opinions or controversial content
- Maximum 2 posts per day
- **All posts require human approval before publishing**

## Configuration
| Env Variable | Default | Description |
|---|---|---|
| `LINKEDIN_ACCESS_TOKEN` | (empty) | OAuth2 access token |
| `LINKEDIN_PERSON_URN` | (empty) | Person URN for author field |
| `LINKEDIN_POST_HOUR` | `10` | Hour to generate daily post |
| `DRY_RUN` | `true` | Skip actual API calls when true |

## Output
Draft files in `Pending_Approval/` with format:
```
YYYYMMDD_HHMMSS_linkedin_post_Topic.md
```
