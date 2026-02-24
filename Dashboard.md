**

# AI Employee Dashboard



Last Updated: 2026-02-24



## Quick Status

- Pending Tasks: 0

- In Progress: 0

- Completed Today: 7

- Needs My Approval: 1



## System Status (Silver Tier — Phase 1.5: Gmail + WhatsApp)

| Component        | Status    | Notes                                                           |
| ---------------- | --------- | --------------------------------------------------------------- |
| Inbox Watcher    | Active    | Polls /Inbox every 5s, moves to /Needs_Action                   |
| Gmail Watcher    | Active    | DRY_RUN=false, interval 60s, scopes: readonly+send+compose      |
| WhatsApp Watcher | Active    | Playwright-based, keyword-matched messages → classify → approve |
| LinkedIn Watcher | Disabled  | Not in ENABLED_WATCHERS (Phase 2)                               |
| Approval Watcher | Active    | Status-based in Obsidian (approved/rejected/revise), Gmail API   |
| Reasoning Engine | Active    | Junk filter + Claude JSON reasoning, routes to Pending_Approval |
| Email Sender     | Active    | Direct Gmail API send/draft (ai_skills/email_sender.py)         |
| LinkedIn Poster  | Disabled  | Skipped when linkedin not in ENABLED_WATCHERS                   |
| Email MCP Server | Available | send_email, draft_email tools (backup, not primary)             |
| MCP Manager      | Active    | On-demand start/stop, 5 min idle auto-shutdown                  |
| Daily Briefing   | Active    | Daily at 8 AM, includes Business_Goals.md context               |
| Scheduler        | Active    | Gmail-related jobs configured                                   |
| Orchestrator     | Active    | Configurable via ENABLED_WATCHERS, auto-restart                 |

## Recent Activity

- [2026-02-24] WhatsApp pipeline integrated — WhatsApp messages now flow through the same classify → draft reply → approve → send pipeline as Gmail. New whatsapp_sender.py (Playwright-based), reasoning engine routes `source: whatsapp` to WhatsApp-specific Claude prompt, approval watcher handles `type: whatsapp_reply`. ENABLED_WATCHERS updated.
- [2026-02-24] Folder cleanup + duplicate fix — Removed 6 duplicate email files from Done/, removed Windows `nul` artifact, empty `Rejected/Plans/` and `Logs/Done/` subfolders cleaned. Gmail watcher now persists seen IDs to `Config/gmail_seen_ids.json` to prevent duplicate processing across restarts.
- [2026-02-24] Silver Tier verified — Full end-to-end test passed: Gmail watcher detects emails, reasoning engine classifies (6 marketing emails correctly archived), approval watcher executes on status change (draft created in Gmail). OAuth re-done with gmail.compose scope. Approval now Obsidian-native (change status field: approved/rejected/revise). Briefing generates on startup.
- [2026-02-18] Full workflow fix — Reasoning engine: real emails now route to Pending_Approval (not Done), junk auto-archives, Claude errors flagged for review. Approval watcher: sends emails via Gmail API directly (no Claude CLI dependency). New email_sender.py module. Improved Claude prompt with few-shot examples. All 6 routing tests pass.
- [2026-02-18] Reasoning Engine rewrite — Email classification (junk auto-archive, Claude JSON reasoning for actionable emails), proper routing to Pending_Approval with approval_watcher-compatible format, Dashboard auto-updates, startup briefing generation, expanded Gmail skip patterns.
- [2026-02-18] Phase 1: Gmail-Only — Fixed MCP credential path (credentials.json -> gmail_credentials.json), aligned Gmail OAuth scopes (added gmail.send), made orchestrator configurable (ENABLED_WATCHERS=inbox,gmail,approval), fixed reasoning engine double-processing (moves tasks to Done after plan creation), set DRY_RUN=false, enhanced daily briefing with Business_Goals.md context.
- [2026-02-18] Gap fixes — Created Business_Goals.md, updated README.md for Silver Tier, fixed .gitignore (added Secrets/, node_modules/, nul), fixed .env paths (GMAIL_CREDENTIALS_PATH, VAULT_PATH), fixed SKILL.md import paths (skills->ai_skills), added zod to package.json.
- [2026-02-18] MCP Manager + bug fixes — on-demand MCP lifecycle, inbox watcher integrated into orchestrator, approval_watcher filepath bug fixed, env var mismatch fixed.
- [2026-02-18] Silver Tier Implementation — All watchers, skills, MCP server, scheduler, and orchestrator created.
- [2026-02-16] Hospital_Image — Reviewed Pexels stock photo of hospital bedside consultation (doctor, nurse, patient). Description added. Moved to /Done.
- [2026-02-16] Hackathon_DOCX — Identified .docx as duplicate of previously-summarized PDF. Noted binary limitation. Moved to /Done.
- [2026-02-16] Bronze_Tier_Roadmap_PDF — Summarized 21-page Bronze Tier Roadmap (7 phases: big picture, install, vault setup, skills, connect Claude, watcher, testing). Moved to /Done.
- [2026-02-16] MRI_Image — Reviewed Siemens MAGNETOM Essenza MRI scanner photo (technician positioning patient). Moved to /Done.
- [2026-02-16] Image_Review — Reviewed and described Canon Lightning Aquilion CT scanner photo (Pexels stock image). Moved to /Done.
- [2026-02-16] New Skill Created — "Summarize PDF" skill added to /Skills/Summarize PDF/SKILL.md.
- [2026-02-16] Hackathon_PDF — Summarized "Personal AI Employee Hackathon 0: Building Autonomous FTEs in 2026" (24-page PDF). Moved to /Done.
- [2026-02-16] TEST_001 — Summarized Q1 revenue report. Moved to /Done.



## Alerts

- Phase 1.5 active — Gmail + WhatsApp (ENABLED_WATCHERS=inbox,gmail,approval,whatsapp)
- DRY_RUN=false — real API calls enabled
- OAuth scopes: gmail.readonly + gmail.send + gmail.compose (token refreshed 2026-02-24)
- To start: `uv run python orchestrator.py` or `start_ai_employee.bat`

**