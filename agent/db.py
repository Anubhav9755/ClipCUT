"""SQLite: the single source of truth for clips, language versions, and posts."""
import json
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS clips (
  id INTEGER PRIMARY KEY, episode_id TEXT, start REAL, end REAL,
  type TEXT, title TEXT, reason TEXT
);
CREATE TABLE IF NOT EXISTS variants (
  id INTEGER PRIMARY KEY, clip_id INTEGER, lang TEXT,
  video_path TEXT, srt_path TEXT,
  title TEXT, caption TEXT, hashtags TEXT,
  needs_review INTEGER DEFAULT 0,
  status TEXT DEFAULT 'pending_review'   -- pending_review / approved / rejected
);
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY, variant_id INTEGER, platform TEXT,
  scheduled_at TEXT,                      -- ISO time in UTC
  status TEXT DEFAULT 'queued',           -- queued / posted / failed
  attempts INTEGER DEFAULT 0, posted_url TEXT, error TEXT
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def clear_episode(conn, episode_id: str) -> None:
    ids = [r["id"] for r in conn.execute("SELECT id FROM clips WHERE episode_id=?", (episode_id,))]
    for cid in ids:
        vids = [r["id"] for r in conn.execute("SELECT id FROM variants WHERE clip_id=?", (cid,))]
        for vid in vids:
            conn.execute("DELETE FROM posts WHERE variant_id=?", (vid,))
        conn.execute("DELETE FROM variants WHERE clip_id=?", (cid,))
    conn.execute("DELETE FROM clips WHERE episode_id=?", (episode_id,))
    conn.commit()


def episode_has_clips(conn, episode_id: str) -> bool:
    return conn.execute("SELECT 1 FROM clips WHERE episode_id=?", (episode_id,)).fetchone() is not None


def add_clip(conn, episode_id, clip) -> int:
    cur = conn.execute(
        "INSERT INTO clips (episode_id,start,end,type,title,reason) VALUES (?,?,?,?,?,?)",
        (episode_id, clip["start"], clip["end"], clip["type"], clip["title"], clip["reason"]),
    )
    conn.commit()
    return cur.lastrowid


def add_variant(conn, clip_id, lang, video_path, srt_path, v) -> int:
    cur = conn.execute(
        "INSERT INTO variants (clip_id,lang,video_path,srt_path,title,caption,hashtags,needs_review)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (clip_id, lang, str(video_path), str(srt_path), v["title"], v["caption"],
         json.dumps(v["hashtags"], ensure_ascii=False), int(v["needs_review"])),
    )
    conn.commit()
    return cur.lastrowid
