"""Step 6: schedule approved clips into daily slots and post them (with retries)."""
import json
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .publishers import get_publisher

MAX_ATTEMPTS = 3
RETRY_DELAY = timedelta(minutes=15)


def _slot_times(cfg, after_utc: datetime):
    """Yield upcoming posting times (UTC), forever, in order."""
    tz = ZoneInfo(cfg["publishing"]["timezone"])
    slots = sorted(cfg["publishing"]["slots"])
    day = after_utc.astimezone(tz).date()
    while True:
        for s in slots:
            h, m = map(int, s.split(":"))
            t = datetime(day.year, day.month, day.day, h, m, tzinfo=tz).astimezone(timezone.utc)
            if t > after_utc:
                yield t
        day += timedelta(days=1)


def schedule_approved(conn, cfg) -> int:
    """Create queued posts for every approved variant that has none. One slot per platform+language."""
    now = datetime.now(timezone.utc)
    created = 0
    variants = conn.execute(
        """SELECT v.* FROM variants v
           WHERE v.status='approved'
             AND NOT EXISTS (SELECT 1 FROM posts p WHERE p.variant_id = v.id)
           ORDER BY v.id"""
    ).fetchall()
    for v in variants:
        for platform in cfg["publishing"]["platforms"]:
            taken = {
                r["scheduled_at"] for r in conn.execute(
                    """SELECT p.scheduled_at FROM posts p JOIN variants x ON x.id=p.variant_id
                       WHERE p.platform=? AND x.lang=?""", (platform, v["lang"]))
            }
            for t in _slot_times(cfg, now):
                iso = t.isoformat()
                if iso not in taken:
                    conn.execute(
                        "INSERT INTO posts (variant_id, platform, scheduled_at) VALUES (?,?,?)",
                        (v["id"], platform, iso))
                    created += 1
                    break
    conn.commit()
    return created


def run_due(conn, cfg) -> int:
    """Post everything that is due. Failed posts are retried up to 3 times, 15 minutes apart."""
    now = datetime.now(timezone.utc)
    due = conn.execute(
        "SELECT * FROM posts WHERE status='queued' AND scheduled_at <= ? ORDER BY scheduled_at",
        (now.isoformat(),)).fetchall()
    done = 0
    for p in due:
        v = dict(conn.execute("SELECT * FROM variants WHERE id=?", (p["variant_id"],)).fetchone())
        v["hashtags"] = json.loads(v["hashtags"])
        try:
            url = get_publisher(p["platform"], cfg["publishing"]["dry_run"]).publish(v)
            conn.execute("UPDATE posts SET status='posted', posted_url=?, attempts=attempts+1, error=NULL "
                         "WHERE id=?", (url, p["id"]))
            done += 1
        except Exception as e:  # keep the loop alive no matter what one platform does
            attempts = p["attempts"] + 1
            if attempts >= MAX_ATTEMPTS:
                conn.execute("UPDATE posts SET status='failed', attempts=?, error=? WHERE id=?",
                             (attempts, str(e), p["id"]))
            else:
                retry_at = (now + RETRY_DELAY).isoformat()
                conn.execute("UPDATE posts SET attempts=?, error=?, scheduled_at=? WHERE id=?",
                             (attempts, str(e), retry_at, p["id"]))
        conn.commit()
    return done


def loop(conn, cfg, every_seconds: int = 60):
    print("Scheduler running. Ctrl+C to stop.")
    while True:
        n = run_due(conn, cfg)
        if n:
            print(f"Posted {n}")
        time.sleep(every_seconds)
