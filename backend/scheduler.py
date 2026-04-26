import asyncio
import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()


async def _daily_content_job():
    from backend.db import get_settings
    from backend.content import generate_post
    from backend.social import publish_post
    from backend.db import update_post_status

    settings = get_settings()
    auto_publish = str(settings.get("auto_publish", "false")).lower() == "true"
    active_themes = settings.get("active_themes", ["daily_special", "ambiance"])
    if isinstance(active_themes, str):
        active_themes = json.loads(active_themes)

    # Filter to non-sport themes for daily job
    themes = [t for t in active_themes if t != "sports_event"]
    if not themes:
        themes = ["daily_special"]

    print("[Scheduler] Generating daily content...")
    post = await generate_post(themes=themes, platforms=["instagram", "facebook"])

    if auto_publish:
        print(f"[Scheduler] Auto-publishing post {post['id']}...")
        await publish_post(post)
        update_post_status(post["id"], "published")
    else:
        print(f"[Scheduler] Post {post['id']} saved as draft, awaiting approval.")


async def _sports_check_job():
    from backend.db import get_settings
    from backend.sports import get_all_upcoming
    from backend.content import generate_post
    from backend.db import get_settings

    settings = get_settings()
    active_themes = settings.get("active_themes", [])
    if isinstance(active_themes, str):
        active_themes = json.loads(active_themes)

    if "sports_event" not in active_themes:
        return

    upcoming = get_all_upcoming()
    from datetime import datetime, timedelta

    # Generate content for events in the next 24h
    now = datetime.now()
    for event in upcoming:
        try:
            event_date = datetime.strptime(event["date_raw"], "%Y-%m-%d")
            diff = (event_date - now).days
            if 0 <= diff <= 1:
                print(f"[Scheduler] Generating sports post for: {event['name']}")
                await generate_post(
                    themes=["sports_event"],
                    event_id=str(event["id"]),
                    platforms=["instagram", "facebook"],
                )
                break  # One sports post per run
        except Exception:
            continue


def setup_scheduler():
    from backend.db import get_settings

    settings = get_settings()
    daily_time = settings.get("daily_story_time", "09:00")
    hour, minute = map(int, daily_time.split(":"))

    scheduler.add_job(
        _daily_content_job,
        CronTrigger(hour=hour, minute=minute),
        id="daily_content",
        replace_existing=True,
    )
    scheduler.add_job(
        _sports_check_job,
        CronTrigger(hour=8, minute=0),
        id="sports_check",
        replace_existing=True,
    )
    scheduler.start()
    print(f"[Scheduler] Started — daily at {daily_time}, sports check at 08:00")
