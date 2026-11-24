"""SQLite for the server. A fresh connection per call keeps threads safe."""
import json
import sqlite3
import time

from . import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  id TEXT PRIMARY KEY, filename TEXT, status TEXT, stage TEXT, progress REAL DEFAULT 0,
  error TEXT, created_at REAL, duration REAL, meta TEXT
);
CREATE TABLE IF NOT EXISTS clips (
  id INTEGER PRIMARY KEY, video_id TEXT, rank INTEGER,
  start REAL, end REAL, pad_start REAL, pad_end REAL,
  title TEXT, reason TEXT, score REAL, source TEXT,
  caption_conf REAL, caption_gate TEXT
);
CREATE TABLE IF NOT EXISTS clip_edits (
  clip_id INTEGER PRIMARY KEY, data TEXT, approved INTEGER DEFAULT 0, updated_at REAL
);
CREATE TABLE IF NOT EXISTS renders (
  clip_id INTEGER PRIMARY KEY, status TEXT, progress REAL DEFAULT 0, error TEXT, output TEXT, updated_at REAL
);
CREATE TABLE IF NOT EXISTS posts (
  clip_id INTEGER PRIMARY KEY, status TEXT, progress REAL DEFAULT 0, error TEXT, url TEXT, updated_at REAL
);
CREATE TABLE IF NOT EXISTS kv (
  key TEXT PRIMARY KEY, value TEXT
);
"""
POST_COLUMNS = {"status": "TEXT", "progress": "REAL DEFAULT 0", "error": "TEXT", "url": "TEXT", "updated_at": "REAL"}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.data_dir() / "clipcut.db", timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    have = {r["name"] for r in conn.execute("PRAGMA table_info(posts)")}
    for col, typ in POST_COLUMNS.items():
        if col not in have:
            conn.execute(f"ALTER TABLE posts ADD COLUMN {col} {typ}")
    return conn


def create_video(video_id: str, filename: str) -> None:
    with connect() as c:
        c.execute("INSERT INTO videos (id, filename, status, stage, created_at, meta) VALUES (?,?,?,?,?,?)",
                  (video_id, filename, "queued", "queued", time.time(), "{}"))


def set_stage(video_id: str, stage: str, progress: float, **meta) -> None:
    with connect() as c:
        row = c.execute("SELECT meta FROM videos WHERE id=?", (video_id,)).fetchone()
        merged = {**json.loads(row["meta"] or "{}"), **meta}
        c.execute("UPDATE videos SET status='processing', stage=?, progress=?, meta=? WHERE id=?",
                  (stage, progress, json.dumps(merged, ensure_ascii=False), video_id))


def set_duration(video_id: str, duration: float) -> None:
    with connect() as c:
        c.execute("UPDATE videos SET duration=? WHERE id=?", (duration, video_id))


def set_done(video_id: str) -> None:
    with connect() as c:
        c.execute("UPDATE videos SET status='done', stage='done', progress=100, error=NULL WHERE id=?", (video_id,))


def set_failed(video_id: str, error: str) -> None:
    with connect() as c:
        c.execute("UPDATE videos SET status='failed', error=? WHERE id=?", (error, video_id))


def requeue(video_id: str) -> None:
    with connect() as c:
        c.execute("UPDATE videos SET status='queued', stage='queued', progress=0, error=NULL WHERE id=?", (video_id,))


def claim_next() -> str | None:
    with connect() as c:
        row = c.execute("SELECT id FROM videos WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
        if not row:
            return None
        cur = c.execute("UPDATE videos SET status='processing' WHERE id=? AND status='queued'", (row["id"],))
        return row["id"] if cur.rowcount else None


def get_video(video_id: str):
    with connect() as c:
        row = c.execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
        return dict(row) if row else None


def list_videos() -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM videos ORDER BY created_at DESC")]


def replace_clips(video_id: str, clips: list[dict]) -> None:
    with connect() as c:
        # clip ids get reused after a re-pick, so old edits must go or they attach to the wrong new clips
        c.execute("DELETE FROM clip_edits WHERE clip_id IN (SELECT id FROM clips WHERE video_id=?)", (video_id,))
        c.execute("DELETE FROM renders WHERE clip_id IN (SELECT id FROM clips WHERE video_id=?)", (video_id,))
        c.execute("DELETE FROM posts WHERE clip_id IN (SELECT id FROM clips WHERE video_id=?)", (video_id,))
        c.execute("DELETE FROM clips WHERE video_id=?", (video_id,))
        for cl in clips:
            c.execute(
                "INSERT INTO clips (video_id, rank, start, end, pad_start, pad_end, title, reason, score, source,"
                " caption_conf, caption_gate) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (video_id, cl["rank"], cl["start"], cl["end"], cl["pad_start"], cl["pad_end"], cl["title"],
                 cl["reason"], cl["score"], cl["source"], cl["caption_conf"], cl["caption_gate"]))


def get_clips(video_id: str) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT clips.*, COALESCE(e.approved, 0) AS approved, COALESCE(r.status, '') AS render_status, "
            "COALESCE(r.progress, 0) AS render_progress, COALESCE(r.error, '') AS render_error, "
            "COALESCE(p.status, '') AS post_status, COALESCE(p.progress, 0) AS post_progress, "
            "COALESCE(p.error, '') AS post_error, COALESCE(p.url, '') AS post_url FROM clips "
            "LEFT JOIN clip_edits e ON e.clip_id = clips.id LEFT JOIN renders r ON r.clip_id = clips.id "
            "LEFT JOIN posts p ON p.clip_id = clips.id "
            "WHERE video_id=? ORDER BY rank", (video_id,))]


def get_clip(clip_id: int):
    with connect() as c:
        row = c.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone()
        return dict(row) if row else None


def get_edit(clip_id: int):
    with connect() as c:
        row = c.execute("SELECT data FROM clip_edits WHERE clip_id=?", (clip_id,)).fetchone()
        return json.loads(row["data"]) if row else None


def save_edit(clip_id: int, data: dict, approved: bool) -> None:
    with connect() as c:
        c.execute("INSERT INTO clip_edits (clip_id, data, approved, updated_at) VALUES (?,?,?,?) "
                  "ON CONFLICT(clip_id) DO UPDATE SET data=excluded.data, approved=excluded.approved, updated_at=excluded.updated_at",
                  (clip_id, json.dumps(data, ensure_ascii=False), int(approved), time.time()))
        c.execute("UPDATE renders SET status='stale' WHERE clip_id=? AND status='done'", (clip_id,))   # edit changed since the render


def get_render(clip_id: int):
    with connect() as c:
        row = c.execute("SELECT * FROM renders WHERE clip_id=?", (clip_id,)).fetchone()
        return dict(row) if row else None


def set_render(clip_id: int, status: str, progress: float, error: str = "", output: str | None = None) -> None:
    with connect() as c:
        c.execute("INSERT INTO renders (clip_id, status, progress, error, output, updated_at) VALUES (?,?,?,?,?,?) "
                  "ON CONFLICT(clip_id) DO UPDATE SET status=excluded.status, progress=excluded.progress, error=excluded.error, "
                  "output=COALESCE(excluded.output, renders.output), updated_at=excluded.updated_at",
                  (clip_id, status, progress, error, output, time.time()))


def fail_stale_renders() -> None:
    """Renders that were queued or running when the server stopped will never finish."""
    with connect() as c:
        c.execute("UPDATE renders SET status='failed', error='Interrupted by a server restart' WHERE status IN ('queued','rendering')")
        c.execute("UPDATE posts SET status='failed', error='Interrupted by a server restart' WHERE status='uploading'")   # same idea for uploads


# ---------- YouTube posts and small saved settings ----------
def get_post(clip_id: int):
    with connect() as c:
        row = c.execute("SELECT * FROM posts WHERE clip_id=?", (clip_id,)).fetchone()
        return dict(row) if row else None


def set_post(clip_id: int, status: str, progress: float = 0, error: str = "", url: str | None = None) -> None:
    with connect() as c:
        c.execute("INSERT INTO posts (clip_id, status, progress, error, url, updated_at) VALUES (?,?,?,?,?,?) "
                  "ON CONFLICT(clip_id) DO UPDATE SET status=excluded.status, progress=excluded.progress, "
                  "error=excluded.error, url=COALESCE(excluded.url, posts.url), updated_at=excluded.updated_at",
                  (clip_id, status, progress, error, url, time.time()))


def get_kv(key: str):
    with connect() as c:
        row = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


def set_kv(key: str, value: str) -> None:
    with connect() as c:
        c.execute("INSERT INTO kv (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))