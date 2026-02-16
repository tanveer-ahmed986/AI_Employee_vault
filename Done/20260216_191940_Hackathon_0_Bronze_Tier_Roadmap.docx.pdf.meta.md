---
source_file: Hackathon_0_Bronze_Tier_Roadmap.docx.pdf
moved_file: 20260216_191940_Hackathon_0_Bronze_Tier_Roadmap.docx.pdf
detected_at: 2026-02-16 19:19:40
type: auto-ingested
priority: normal
status: completed
---

## Auto-Ingested File

**Original filename:** Hackathon_0_Bronze_Tier_Roadmap.docx.pdf
**Detected:** 2026-02-16 19:19:40

## Suggested Actions

  - Review document
  - Extract key information

## Summary

**Overview:** A complete beginner-friendly, step-by-step roadmap for building a personal AI Employee (Bronze Tier) using Claude Code, Obsidian, and a Python file watcher — part of the Panaversity Personal AI Employee Hackathon 0.

**Document Type:** guide / tutorial roadmap

**Page Count:** 21

**Key Points:**

- **Phase 1 (30 min):** Understand the big picture — the AI Employee has 3 parts: The Brain (Claude Code), The Memory/GUI (Obsidian), and The Eyes (Python Watcher Script). File flow: Inbox → Needs_Action → Plans → Done.

- **Phase 2 (2-3 hrs):** Install 5 tools — Obsidian, Python 3.13+, Node.js v24+, Claude Code (`npm install -g @anthropic/claude-code`), and GitHub Desktop. Critical: check "Add Python to PATH" on Windows.

- **Phase 3 (1 hr):** Create the Obsidian vault with 9 folders (Inbox, Needs_Action, Plans, Done, Logs, Skills, Pending_Approval, Approved, Rejected) plus key files: Dashboard.md, Company_Handbook.md, and CLAUDE.md (the most important file — auto-read by Claude on every run).

- **Phase 4 (1 hr):** Create Agent Skills — reusable SKILL.md instruction files in /Skills/ folders. Two starter skills: "Summarize File" and "Process Task". Skills make Claude consistent and reliable.

- **Phase 5 (1 hr):** Connect Claude Code to the vault — open terminal in vault folder, run `claude`, test read/write/full workflow by creating a test task and processing it.

- **Phase 6 (2-3 hrs):** Build the file watcher using Python's `watchdog` library — a single `file_watcher.py` script that monitors /Inbox, moves new files to /Needs_Action with timestamp prefixes, and creates .meta.md metadata files.

- **Phase 7 (1-2 hrs):** Test the full system (5 tests: .txt file, image file, 3-file batch, Dashboard check, Logs check), save to GitHub with .gitignore, record 5-10 min demo video, write README.md, and submit.

- **Bonus:** Ralph Wiggum Loop — optional automation that keeps Claude running in a loop, automatically processing tasks until /Needs_Action is empty, with a completion promise and max-iterations safety limit.

**Important Details:**

- Estimated total time: 8-12 hours for absolute beginners
- Submission form: Google Forms link provided
- Support: Wednesday Zoom meetings for troubleshooting
- The system runs with 2 terminals: Terminal 1 for the Watcher, Terminal 2 for Claude Code

**Action Items:**

- [ ] Ensure all 5 tools are installed and verified
- [ ] Complete all 7 phases in order
- [ ] Run all 5 system tests before submitting
- [ ] Record demo video and publish to GitHub
- [ ] Submit via Google Forms
