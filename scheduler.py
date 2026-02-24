"""Scheduler — runs recurring jobs: daily briefing, LinkedIn post gen, task processing."""

import logging
import time
from datetime import datetime

import schedule

import config
from ai_skills.reasoning_engine import ReasoningEngine

logger = logging.getLogger("scheduler")


def daily_briefing():
    """Generate a daily briefing summarizing pending tasks and recent activity."""
    logger.info("Running daily briefing")
    now = datetime.now()

    # Count pending tasks
    pending_count = sum(
        1
        for d in [
            config.NEEDS_ACTION_DIR,
            config.NEEDS_ACTION_EMAIL,
            config.NEEDS_ACTION_WHATSAPP,
            config.NEEDS_ACTION_LINKEDIN,
        ]
        if d.exists()
        for f in d.glob("*.md")
    )

    # Count items waiting approval
    approval_count = sum(1 for f in config.PENDING_APPROVAL_DIR.glob("*.md")) if config.PENDING_APPROVAL_DIR.exists() else 0

    # Count completed today
    today_str = now.strftime("%Y%m%d")
    done_today = sum(1 for f in config.DONE_DIR.iterdir() if f.is_file() and f.name.startswith(today_str)) if config.DONE_DIR.exists() else 0

    # Read business goals for context
    business_goals_section = ""
    goals_path = config.VAULT_PATH / "Business_Goals.md"
    if goals_path.exists():
        try:
            goals_text = goals_path.read_text(encoding="utf-8")
            # Extract Current Priorities section
            priorities = []
            in_priorities = False
            for line in goals_text.splitlines():
                if "## Current Priorities" in line:
                    in_priorities = True
                    continue
                if in_priorities:
                    if line.startswith("## "):
                        break
                    stripped = line.strip()
                    if stripped and not stripped.startswith("<!--"):
                        priorities.append(stripped)
            # Extract mission statement
            mission = ""
            for line in goals_text.splitlines():
                if line.startswith("Deliver") or (line.strip() and not line.startswith("#") and not line.startswith("-") and not line.startswith("|") and not line.startswith("<!--") and not line.startswith("---") and "mission" not in line.lower() and "last_updated" not in line and "updated_by" not in line and len(line.strip()) > 20):
                    mission = line.strip()
                    break
            if mission or priorities:
                business_goals_section = "## Business Context\n"
                if mission:
                    business_goals_section += f"**Mission:** {mission}\n"
                if priorities:
                    business_goals_section += "**Current Priorities:**\n"
                    for p in priorities:
                        business_goals_section += f"  {p}\n"
                business_goals_section += "\n"
        except Exception:
            logger.warning("Could not read Business_Goals.md")

    briefing = (
        f"---\n"
        f"type: daily_briefing\n"
        f"date: {now.strftime('%Y-%m-%d')}\n"
        f"generated_at: {now.isoformat()}\n"
        f"---\n\n"
        f"# Daily Briefing — {now.strftime('%A, %B %d, %Y')}\n\n"
        f"{business_goals_section}"
        f"## Summary\n"
        f"- **Pending tasks:** {pending_count}\n"
        f"- **Awaiting approval:** {approval_count}\n"
        f"- **Completed today:** {done_today}\n\n"
        f"## Action Items\n"
    )

    if pending_count > 0:
        briefing += f"- [ ] Process {pending_count} pending task(s)\n"
    if approval_count > 0:
        briefing += f"- [ ] Review {approval_count} item(s) awaiting approval\n"
    if pending_count == 0 and approval_count == 0:
        briefing += "- All clear! No pending actions.\n"

    path = config.BRIEFINGS_DIR / f"briefing_{now.strftime('%Y%m%d')}.md"
    path.write_text(briefing, encoding="utf-8")
    logger.info("Daily briefing saved: %s", path.name)


def generate_linkedin_post():
    """Use Claude to draft a LinkedIn post, saved for approval."""
    if "linkedin" not in config.ENABLED_WATCHERS:
        logger.debug("LinkedIn not in ENABLED_WATCHERS — skipping post generation")
        return
    logger.info("Generating LinkedIn post draft")
    from ai_skills.linkedin_poster import LinkedInPoster
    poster = LinkedInPoster()

    if config.DRY_RUN:
        content = (
            "🚀 [DRY RUN] This is a placeholder LinkedIn post.\n\n"
            "In production, Claude would generate a professional post "
            "based on recent business activity and industry trends."
        )
    else:
        import subprocess
        try:
            result = subprocess.run(
                [
                    "claude", "--print", "-p",
                    "Generate a short professional LinkedIn post (under 200 words) "
                    "about AI automation in business. Be insightful and engaging. "
                    "Do not use hashtags excessively. Output only the post text.",
                ],
                capture_output=True, text=True, timeout=60,
                cwd=str(config.VAULT_PATH),
            )
            content = result.stdout.strip() or "[ERROR] No output from Claude"
        except Exception as e:
            logger.exception("Failed to generate LinkedIn post")
            content = f"[ERROR] {e}"

    poster.create_post_draft(content, topic="AI_Automation")


def process_needs_action():
    """Run the reasoning engine on all pending Needs_Action files."""
    engine = ReasoningEngine()
    plans = engine.process_all()
    if plans:
        logger.info("Processed %d task(s) into plans", len(plans))


def start_scheduler():
    """Configure and run the scheduler (blocking)."""
    logger.info("Scheduler starting")

    schedule.every().day.at(f"{config.BRIEFING_HOUR:02d}:00").do(daily_briefing)
    schedule.every().monday.at(f"{config.LINKEDIN_POST_HOUR:02d}:00").do(generate_linkedin_post)
    schedule.every().tuesday.at(f"{config.LINKEDIN_POST_HOUR:02d}:00").do(generate_linkedin_post)
    schedule.every().wednesday.at(f"{config.LINKEDIN_POST_HOUR:02d}:00").do(generate_linkedin_post)
    schedule.every().thursday.at(f"{config.LINKEDIN_POST_HOUR:02d}:00").do(generate_linkedin_post)
    schedule.every().friday.at(f"{config.LINKEDIN_POST_HOUR:02d}:00").do(generate_linkedin_post)
    schedule.every(config.PROCESSING_INTERVAL_MIN).minutes.do(process_needs_action)

    logger.info(
        "Scheduled: briefing@%02d:00, linkedin@%02d:00 weekdays, processing every %d min",
        config.BRIEFING_HOUR, config.LINKEDIN_POST_HOUR, config.PROCESSING_INTERVAL_MIN,
    )

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    start_scheduler()
