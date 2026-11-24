"""End-to-end test with a fake video, fake transcript and a fake AI (no API key or Whisper needed).

Run from the project folder:  python tests/smoke_test.py
"""
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent import config as cfgmod, db, llm, review, scheduler  # noqa: E402
import pipeline  # noqa: E402

tmp = Path(tempfile.mkdtemp())
video = tmp / "episode.mp4"
subprocess.run([
    "ffmpeg", "-y", "-loglevel", "error",
    "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:duration=60",
    "-f", "lavfi", "-i", "sine=frequency=440:duration=60",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video)], check=True)

cfg = cfgmod.load()
cfg["paths"] = {"work_dir": str(tmp / "work"), "db": str(tmp / "t.db"), "review_csv": str(tmp / "review.csv")}
cfg["languages"] = ["en", "hi"]
cfg["clips"]["per_episode"] = 2

# fake transcript (what Whisper would have produced)
work = Path(cfg["paths"]["work_dir"]) / "ep01"
work.mkdir(parents=True)
cues = [{"start": 2 + i * 3, "end": 4.8 + i * 3, "text": f"Line number {i + 1} of the dialogue"} for i in range(18)]
segs = [{"start": 2, "end": 30, "text": "first half"}, {"start": 31, "end": 58, "text": "second half"}]
(work / "transcript.json").write_text(json.dumps({"segments": segs, "cues": cues}), encoding="utf-8")


# fake AI
def fake_ask_json(model, system, user, max_tokens=4000):
    if "Pick up to" in user:
        return [
            {"start": 2, "end": 30, "type": "short", "title": "Clever comeback", "reason": "punchline"},
            {"start": 31, "end": 58, "type": "promo", "title": "Cliffhanger", "reason": "teaser"},
            {"start": 10, "end": 20, "type": "short", "title": "overlaps + too short", "reason": ""},
        ]
    n = int(user.split("Dialogue lines to translate (")[1].split(" lines")[0])
    lang = user.split("Target language: ")[1].split("\n")[0]
    return {"title": f"Title ({lang})", "caption": f"Caption ({lang}) \U0001F602 Watch more!",
            "hashtags": ["TenaliRama", "Animation"], "subtitles": [f"[{lang}] line {i + 1}" for i in range(n)]}


llm.ask_json = fake_ask_json

conn = db.connect(cfg["paths"]["db"])
pipeline.process(cfg, conn, video, "ep01", force=False)

variants = conn.execute("SELECT * FROM variants").fetchall()
assert len(conn.execute("SELECT * FROM clips").fetchall()) == 2, "bad clips were not filtered out"
assert len(variants) == 4, f"expected 4 variants, got {len(variants)}"
for v in variants:
    assert Path(v["video_path"]).stat().st_size > 10_000, "video missing or empty"
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", v["video_path"]],
                           capture_output=True, text=True).stdout.strip()
    assert probe == "1080,1920", f"not 9:16: {probe}"

# review: approve everything in the exported CSV
rows = list(csv.DictReader(open(cfg["paths"]["review_csv"], encoding="utf-8-sig")))
assert len(rows) == 4
for r in rows:
    r["decision"] = "approve"
with open(cfg["paths"]["review_csv"], "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=review.COLUMNS)
    w.writeheader()
    w.writerows(rows)
assert review.import_csv(conn, cfg["paths"]["review_csv"])["approved"] == 4

# schedule + post (dry run). Pull the posts into the past so they are due now.
cfg["publishing"]["dry_run"] = True
queued = scheduler.schedule_approved(conn, cfg)
assert queued == 4 * len(cfg["publishing"]["platforms"]), queued
conn.execute("UPDATE posts SET scheduled_at='2000-01-01T00:00:00+00:00'")
conn.commit()
posted = scheduler.run_due(conn, cfg)
assert posted == queued, (posted, queued)

# a platform that is not connected must fail gracefully and retry, not crash
cfg["publishing"]["dry_run"] = False
conn.execute("UPDATE posts SET status='queued', attempts=0, scheduled_at='2000-01-01T00:00:00+00:00' WHERE platform='x'")
conn.commit()
scheduler.run_due(conn, cfg)
r = conn.execute("SELECT status, attempts, error FROM posts WHERE platform='x' LIMIT 1").fetchone()
assert r["status"] == "queued" and r["attempts"] == 1 and "not connected" in r["error"], dict(r)

print("\nALL CHECKS PASSED")
shutil.copy(next(Path(cfg["paths"]["work_dir"]).glob("ep01/clip01_hi/*.mp4")), "/home/claude/sample_clip.mp4")
shutil.rmtree(tmp)
