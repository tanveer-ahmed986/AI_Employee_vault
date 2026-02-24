# Skill: Reasoning Engine

## Description
Scans `/Needs_Action/` for task files, sends them to Claude Code for reasoning, and generates plan files in `/Plans/`.

## Trigger
- Scheduled: every 5 minutes (configurable via `PROCESSING_INTERVAL_MIN`)
- Manual: `uv run python -c "from ai_skills.reasoning_engine import ReasoningEngine; e = ReasoningEngine(); e.process_all()"`

## What It Does
1. Scans all `Needs_Action/` subdirectories (Email, WhatsApp, LinkedIn, root) for `.md` files
2. For each task file, constructs a prompt with the file content
3. Sends prompt to Claude Code CLI (`claude --print -p`)
4. Claude generates a step-by-step plan with:
   - Objective
   - Context
   - Steps (numbered checkboxes)
   - Approval requirements
5. Saves the plan as `PLAN_[taskname].md` in `/Plans/`
6. Logs the action as JSON in `/Logs/YYYY-MM-DD.jsonl`

## DRY_RUN Mode
When `DRY_RUN=true`, generates a placeholder plan without calling Claude CLI.

## Configuration
| Env Variable | Default | Description |
|---|---|---|
| `PROCESSING_INTERVAL_MIN` | `5` | Minutes between processing runs |
| `DRY_RUN` | `true` | Skip Claude CLI calls when true |

## Output
- Plan files in `Plans/PLAN_[taskname].md`
- JSON logs in `Logs/YYYY-MM-DD.jsonl`
