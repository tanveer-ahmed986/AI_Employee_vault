# Personal AI Employee (Atlas)

A local-first, autonomous AI Employee that lives inside an Obsidian vault. Drop a file in, and Atlas reads it, plans, executes, organizes, and logs — all automatically.

**Tier:** Bronze
**Hackathon:** Panaversity Personal AI Employee Hackathon 0
**Owner:** Tanveer Ahmed

## Architecture

The system has three components working together:

| Component | Role | Tool |
|-----------|------|------|
| **The Brain** | Reads tasks, makes plans, writes summaries | Claude Code |
| **The Memory / GUI** | Stores everything as files, provides dashboard | Obsidian |
| **The Eyes** | Watches for new files dropped into /Inbox | Python (watchdog) |

**Agent Skills** are reusable SKILL.md instruction files that make Claude consistent. Each skill lives in `/Skills/` and contains step-by-step instructions for a specific task type (summarizing files, processing tasks, summarizing PDFs, etc.).

## File Flow

```
/Inbox          You drop files here
   |
   v  (file_watcher.py detects and moves with timestamp prefix + metadata)
/Needs_Action   Claude picks up tasks from here
   |
   v  (Claude reads task, creates plan)
/Plans          Action plans before execution
   |
   v  (Claude executes plan, writes summary)
/Done           Completed tasks land here
```

Claude also updates `/Dashboard.md` and writes to `/Logs/` after every task.

Sensitive tasks (payments, deletes, external sends) are routed to `/Pending_Approval` for human review.

## Folder Structure

```
AI_Employee_vault/
├── Inbox/              <- Drop files here
├── Needs_Action/       <- Watcher moves files here for Claude
├── Plans/              <- Claude writes action plans here
├── Done/               <- Completed tasks + plans
├── Logs/               <- Daily activity logs
├── Skills/             <- Agent Skill files (SKILL.md)
├── Pending_Approval/   <- Tasks needing human sign-off
├── Approved/           <- Human-approved tasks
├── Rejected/           <- Human-rejected tasks
├── Dashboard.md        <- Real-time status board
├── Company_Handbook.md <- Rules for the AI
├── CLAUDE.md           <- Master instructions (auto-read by Claude)
└── file_watcher.py     <- Inbox watcher script
```

## Setup Instructions

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Obsidian | Latest | Vault GUI and file management |
| Python | 3.13+ | Runs the watcher script |
| Node.js | v24+ | Required for Claude Code |
| Claude Code | Latest | AI brain (`npm install -g @anthropic/claude-code`) |

### Install

1. Clone this repo:
   ```bash
   git clone https://github.com/tanveer-ahmed986/AI_Employee_vault.git
   ```

2. Open the folder as an Obsidian vault (Obsidian > Open folder as vault)

3. Install the Python watcher dependency:
   ```bash
   pip install watchdog
   ```

4. Update `VAULT_PATH` in `file_watcher.py` to your local vault path

5. Install Claude Code (if not already):
   ```bash
   npm install -g @anthropic/claude-code
   ```

## How to Run

Open **two terminals**, both pointed at the vault folder:

**Terminal 1 — File Watcher** (leave running):
```bash
cd /path/to/AI_Employee_vault
python file_watcher.py
```

**Terminal 2 — Claude Code**:
```bash
cd /path/to/AI_Employee_vault
claude
```

Then tell Claude:
```
Process all tasks in /Needs_Action following CLAUDE.md.
Use skills from /Skills/. Update Dashboard.md when done.
```

Or use the Ralph Wiggum Loop for fully autonomous processing:
```
/ralph-loop "Process all files in /Needs_Action following CLAUDE.md. \
Use skills from /Skills/. Update Dashboard.md." \
--completion-promise "TASK_COMPLETE" \
--max-iterations 10
```

## Agent Skills

| Skill | Location | Purpose |
|-------|----------|---------|
| Process Task | `/Skills/Process Task/SKILL.md` | General task processing workflow |
| Summarize File | `/Skills/Summarize File/SKILL.md` | Summarize text/document files |
| Summarize PDF | `/Skills/Summarize PDF/SKILL.md` | PDF-specific summarization with multi-page support |

## Security

Sensitive files are excluded from version control via `.gitignore`:

```
.env
credentials.json
__pycache__/
.obsidian/
*.secret
*.token
```

- No API keys or credentials are stored in the repo
- `.obsidian/` settings are local-only (not committed)
- Sensitive tasks are routed to `/Pending_Approval` for human review before execution
- The AI Employee never sends messages, makes payments, or deletes files without human approval
