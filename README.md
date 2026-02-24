# Personal AI Employee (Atlas)

A local-first, autonomous AI Employee that lives inside an Obsidian vault. Atlas monitors Gmail, WhatsApp, and LinkedIn, reasons about incoming tasks, executes approved actions through MCP servers, and runs on a daily schedule -- all with human-in-the-loop safety.

**Tier:** Silver (Functional Assistant) -- COMPLETE
**Hackathon:** Panaversity Personal AI Employee Hackathon 0
**Owner:** Tanveer Ahmed

## Silver Tier Completion

All 9 phases implemented and verified:

| Phase | Requirement | Status |
|-------|------------|--------|
| 1 | Bronze foundation (vault, Dashboard, Handbook, folders) | Done |
| 2 | Multiple watchers (Gmail + WhatsApp + LinkedIn) | Done |
| 3 | LinkedIn auto-posting for sales | Done |
| 4 | Claude reasoning loop + Plan.md | Done |
| 5 | MCP server (Email) | Done |
| 6 | Human-in-the-loop approval workflow | Done |
| 7 | Basic scheduling (daily briefing, task processing) | Done |
| 8 | Agent Skills (11 SKILL.md files + registry) | Done |
| 9 | Integration testing (end-to-end verified) | Done |

**End-to-end pipelines:**
- **Gmail:** detect unread email -> Claude classifies -> draft reply in Pending_Approval -> user approves in Obsidian -> Gmail API sends/drafts
- **WhatsApp:** detect keyword-matched message -> Claude classifies -> draft reply in Pending_Approval -> user approves -> Playwright sends via WhatsApp Web
- **LinkedIn:** scheduled post generation -> draft in Pending_Approval -> user approves -> LinkedIn API publishes

## Architecture

The Silver Tier follows the **Perception -> Reasoning -> Action** pattern:

```
Perception Layer:
    Gmail Watcher + WhatsApp Watcher + LinkedIn Watcher + Inbox Watcher
        --> /Needs_Action/

Reasoning Layer:
    Reasoning Engine reads /Needs_Action/  -->  creates /Plans/  -->  decides actions

Action Layer:
    MCP Servers execute approved actions  -->  results logged to /Logs/  -->  files moved to /Done/

Safety Layer:
    Sensitive actions go to /Pending_Approval/  -->  Human moves to /Approved/  -->  then executed
```

| Component            | Role                                                  | Tool              |
| -------------------- | ----------------------------------------------------- | ----------------- |
| **The Brain**        | Reads tasks, makes plans, writes summaries            | Claude Code       |
| **The Memory / GUI** | Stores everything as files, provides dashboard        | Obsidian          |
| **The Eyes**         | Watches Gmail, WhatsApp, LinkedIn, and /Inbox         | Python watchers   |
| **The Hands**        | Sends emails, posts to LinkedIn via MCP               | MCP Servers       |
| **The Scheduler**    | Runs daily briefings, LinkedIn posts, task processing | Python (schedule) |
| **The Gatekeeper**   | Approval workflow for sensitive actions               | Approval Watcher  |

## File Flow

```
External Sources              /Inbox
(Gmail, WhatsApp, LinkedIn)    (manual file drops)
        |                          |
        v                          v  (inbox_watcher moves with timestamp + metadata)
/Needs_Action/Email/          /Needs_Action/
/Needs_Action/WhatsApp/
/Needs_Action/LinkedIn/
        |
        v  (Reasoning Engine reads task, creates plan)
/Plans/PLAN_[taskname].md
        |
        +-- Safe actions --> Execute --> /Done
        |
        +-- Sensitive actions --> /Pending_Approval
                                       |
                                 Human moves to /Approved or /Rejected
                                       |
                                       v  (Approval Watcher triggers MCP)
                                 /Done  +  /Logs/
```

## Folder Structure

```
AI_Employee_vault/
├── watchers/               <- Watcher modules (Gmail, WhatsApp, LinkedIn, Inbox)
│   ├── base_watcher.py     <- Abstract base class
│   ├── gmail_watcher.py    <- Gmail API monitoring
│   ├── whatsapp_watcher.py <- Playwright-based WhatsApp Web
│   ├── linkedin_watcher.py <- LinkedIn API monitoring
│   └── inbox_watcher.py    <- Local /Inbox folder monitoring
├── ai_skills/              <- AI skill implementations
│   ├── reasoning_engine.py <- Claude CLI reasoning loop (Gmail + WhatsApp classification)
│   ├── email_sender.py     <- Direct Gmail API send/draft
│   ├── whatsapp_sender.py  <- Playwright-based WhatsApp reply sender
│   └── linkedin_poster.py  <- LinkedIn post drafting + publishing
├── mcp_servers/
│   └── email_mcp/          <- Node.js Email MCP server (send_email, draft_email)
├── Skills/                 <- Agent Skill documentation (SKILL.md files)
│   └── SKILL_REGISTRY.md   <- Master skill index
├── Inbox/                  <- Drop files here
├── Needs_Action/           <- Watchers move items here for processing
│   ├── Email/
│   ├── WhatsApp/
│   └── LinkedIn/
├── Plans/                  <- Reasoning Engine generates plans here
├── Done/                   <- Completed tasks archive
├── Pending_Approval/       <- Tasks needing human sign-off
├── Approved/               <- Human-approved tasks (triggers execution)
├── Rejected/               <- Human-rejected tasks
├── Logs/                   <- Daily activity logs + JSON audit trail
├── Briefings/              <- Generated daily CEO briefings
├── Templates/              <- Plan and post templates
├── Config/                 <- Configuration files
├── config.py               <- Central configuration loader
├── orchestrator.py         <- Daemon thread manager for all watchers
├── scheduler.py            <- Scheduled jobs (briefing, LinkedIn, processing)
├── approval_watcher.py     <- Watches /Approved, triggers MCP actions
├── mcp_manager.py          <- On-demand MCP server lifecycle manager
├── Dashboard.md            <- Real-time status board
├── Company_Handbook.md     <- Rules for the AI
├── Business_Goals.md       <- Business objectives (used by briefing + LinkedIn poster)
├── CLAUDE.md               <- Master instructions (auto-read by Claude)
└── start_ai_employee.bat   <- Windows launcher script
```

## Prerequisites

| Tool        | Version | Purpose                                            |
| ----------- | ------- | -------------------------------------------------- |
| Obsidian    | Latest  | Vault GUI and file management                      |
| Python      | 3.13+   | Watchers, scheduler, orchestrator                  |
| Node.js     | v24+    | MCP server + Claude Code                           |
| Claude Code | Latest  | AI brain (`npm install -g @anthropic/claude-code`) |
| UV          | Latest  | Python project/dependency management               |

## Setup

1. Clone this repo:
   ```bash
   git clone https://github.com/tanveer-ahmed986/AI_Employee_vault.git
   cd AI_Employee_vault
   ```

2. Open the folder as an Obsidian vault (Obsidian > Open folder as vault)

3. Create a `.env` file in the vault root (see `.env.example` or the Silver Tier guide):
   ```
   GMAIL_CLIENT_ID=your_client_id
   GMAIL_CLIENT_SECRET=your_client_secret
   GMAIL_CREDENTIALS_PATH=path/to/credentials.json
   LINKEDIN_ACCESS_TOKEN=your_token
   LINKEDIN_PERSON_URN=urn:li:person:YOUR_ID
   VAULT_PATH=D:\AI_Employee\AI_Employee_vault
   DRY_RUN=true
   DEV_MODE=true
   ```

4. Install Python dependencies:
   ```bash
   uv sync
   ```

5. Install MCP server dependencies:
   ```bash
   cd mcp_servers/email_mcp && npm install && cd ../..
   ```

6. Install Playwright browser (for WhatsApp watcher):
   ```bash
   uv run playwright install chromium
   ```

7. Set up Gmail OAuth (follow the Silver Tier guide for credential setup)

## How to Run

### Option A: Full Orchestrator (recommended)
Start everything with one command:
```bash
start_ai_employee.bat
```
Or directly:
```bash
uv run python orchestrator.py
```
This launches all watchers, the scheduler, and the approval watcher as daemon threads with auto-restart.

### Option B: Manual Claude Code session
```bash
cd AI_Employee_vault
claude
```
Then tell Claude to process tasks following CLAUDE.md.

## System Components

| Component        | Schedule/Trigger | What It Does                                      |
| ---------------- | ---------------- | ------------------------------------------------- |
| Inbox Watcher    | Every 5s         | Moves /Inbox files to /Needs_Action with metadata |
| Gmail Watcher    | Every 60s        | Monitors unread important emails                  |
| WhatsApp Watcher | Every 30s        | Monitors keyword-matched WhatsApp messages        |
| WhatsApp Sender  | On approve       | Sends replies via WhatsApp Web (Playwright)       |
| LinkedIn Watcher | Every 5 min      | Monitors LinkedIn notifications/messages          |
| Reasoning Engine | Every 5 min      | Generates Plan.md from /Needs_Action items        |
| LinkedIn Poster  | 10 AM weekdays   | Drafts LinkedIn posts for approval                |
| Daily Briefing   | 8 AM daily       | Generates CEO briefing report                     |
| Approval Watcher | Every 10s        | Executes approved actions via MCP                 |
| MCP Manager      | On demand        | Starts/stops MCP servers, 5 min idle timeout      |

## Agent Skills

| Skill            | Category   | Trigger           |
| ---------------- | ---------- | ----------------- |
| Gmail Watcher    | Perception | Continuous        |
| WhatsApp Watcher | Perception | Continuous        |
| LinkedIn Watcher | Perception | Continuous        |
| Reasoning Engine | Reasoning  | Every 5 min       |
| LinkedIn Poster  | Action     | Scheduled (10 AM) |
| Email Sender     | Action     | On demand (MCP)   |
| WhatsApp Sender  | Action     | On approve        |
| Daily Briefing   | Reporting  | Scheduled (8 AM)  |
| Process Task     | Processing | Manual            |
| Summarize File   | Processing | Manual            |
| Summarize PDF    | Processing | Manual            |

See `Skills/SKILL_REGISTRY.md` for full details.

## Security

- `.env` with all credentials is excluded from git via `.gitignore`
- `Secrets/` folder is git-ignored
- `DRY_RUN=true` prevents real API calls during development
- All sensitive actions (payments, emails, social posts) require human approval
- Audit logging for every external action in `/Logs/`
- MCP servers run on-demand only, auto-shutdown after 5 min idle
- No credentials stored in vault markdown files
