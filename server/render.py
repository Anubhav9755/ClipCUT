"""Render approved clips to 1080x1920 MP4 with ffmpeg (captions come later).

The saved edit (trim + crop keyframes) is applied to the ORIGINAL video, not the 720p preview.
Runs in one background thread so the web page never freezes; progress is stored in the database."""
import os
import queue
import shutil
import subprocess
import tempfile
import threading
from fractions import Fraction
from pathlib import Path

from . import captions as caps
from . import db, settings

OUT_W, OUT_H = 1080, 1920
_q: "queue.Queue[int]" = queue.Queue()
_started = False
_lock = threading.Lock()


# ---------- crop path ----------
def x_at(kfs: list[dict], t: float) -> float:
    """Window position (0..1) at time t. A keyframe's mode says how we ARRIVE at it:
    'cut' = jump there, 'pan' = smooth glide from the previous keyframe. Same rule as the editor."""
    k = sorted(kfs, key=lambda q: q["t"])
    if not k:
        return 0.5
    if t <= k[0]["t"]:
        return k[0]["x"]
    i = 0
    while i + 1 < len(k) and k[i + 1]["t"] <= t:
        i += 1
    if i + 1 >= len(k) or k[i + 1]["mode"] == "cut":
        return k[i]["x"]
    u = (t - k[i]["t"]) / (k[i + 1]["t"] - k[i]["t"])
    s = u * u * (3 - 2 * u)
    return k[i]["x"] + (k[i + 1]["x"] - k[i]["x"]) * s


def x_expression(kfs: list[dict], start: float, end: float, span: int) -> str:
    """ffmpeg expression (in pixels, using t = seconds since the clip start) for the crop window's x."""
    dur = end - start
    pts = [(0.0, round(x_at(kfs, start) * span), "cut")]
    for q in sorted(kfs, key=lambda q: q["t"]):
        if start + 0.02 < q["t"] < end - 0.02:
            pts.append((q["t"] - start, round(q["x"] * span), q["mode"]))
    segs = []                                   # (until_t, expression)
    for (t0, p0, _), (t1, p1, m1) in zip(pts, pts[1:]):
        if m1 == "pan" and t1 - t0 > 0.02:
            d = t1 - t0
            segs.append((t1, f"{p0}+({p1 - p0})*pow((t-{t0:.3f})/{d:.3f},2)*(3-2*(t-{t0:.3f})/{d:.3f})"))
        else:
            segs.append((t1, str(p0)))          # hold, then jump at t1
    expr = str(pts[-1][1])
    for t_end, e in reversed(segs):
        expr = f"if(lt(t,{t_end:.3f}),{e},{expr})"
    return expr


# ---------- ffmpeg ----------
def _tool(name: str) -> str:
    p = shutil.which(name)
    if not p:
        raise RuntimeError(f"{name} was not found on PATH")
    return p


def _probe(src: Path) -> dict:
    import json
    ffprobe = _tool("ffprobe")
    r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "stream=codec_type,width,height,avg_frame_rate,r_frame_rate",
                        "-of", "json", str(src)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    streams = json.loads(r.stdout or "{}").get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not v:
        raise RuntimeError("No video stream found in the original file")
    fps = None
    for key in ("avg_frame_rate", "r_frame_rate"):
        try:
            f = Fraction(v.get(key, "0/1"))
            if 1 <= f <= 120:
                fps = f
                break
        except (ZeroDivisionError, ValueError):
            pass
    return {"w": int(v["width"]), "h": int(v["height"]), "fps": fps,
            "audio": any(s.get("codec_type") == "audio" for s in streams)}


def render_file(src: Path, edit: dict, out: Path, progress=lambda pct: None, cues: list | None = None, font: Path | None = None) -> None:
    """Cut, crop, scale and loudness-normalise one clip. Raises RuntimeError with a readable message."""
    src, out = Path(src).resolve(), Path(out).resolve()      # ffmpeg runs in a temp folder, so paths must be absolute
    info = _probe(src)
    W, H = info["w"], info["h"]
    cw = int(H * 9 / 16) // 2 * 2
    if cw > W:
        raise RuntimeError("The original video is already narrower than 9:16")
    start, end = max(0.0, float(edit["start"])), float(edit["end"])
    dur = end - start
    if dur < 1:
        raise RuntimeError("The trimmed clip is shorter than 1 second")
    fps = info["fps"] or Fraction(str(edit.get("fps", 25))).limit_denominator(1001)

    expr = x_expression(edit["keyframes"], start, end, W - cw)
    graph = (f"crop=w={cw}:h={H}:x='{expr}':y=0:exact=1,"
             f"scale={OUT_W}:{OUT_H}:flags=lanczos")
    workdir = Path(tempfile.mkdtemp(prefix="clipcut_"))
    if cues:                                    # burned-in captions; ffmpeg runs inside workdir so the paths stay simple
        caps.write_ass(cues, start, workdir, font)
        graph += ",ass=filename=cap.ass" + (":fontsdir=fonts" if font else "")
    graph += ",setsar=1,format=yuv420p"
    ffmpeg = _tool("ffmpeg")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.mp4")
    log = out.with_suffix(".log")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fs:
        fs.write(graph)
        script = fs.name
    cmd = [ffmpeg, "-y", "-hide_banner", "-nostats", "-loglevel", "error", "-progress", "pipe:1",
           "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
           "-filter_script:v", script, "-r", f"{fps.numerator}/{fps.denominator}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
    if info["audio"]:
        cmd += ["-af", "aresample=async=1:first_pts=0,loudnorm=I=-16:TP=-1.5:LRA=11",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", str(tmp)]
    try:
        with open(log, "w", encoding="utf-8") as lf:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=lf, text=True, encoding="utf-8", errors="replace", cwd=str(workdir))
            for line in p.stdout:
                if line.startswith(("out_time_us=", "out_time_ms=")):
                    try:
                        progress(min(99.0, float(line.split("=")[1]) / 1e6 / dur * 100))
                    except ValueError:
                        pass
            p.wait()
        if p.returncode != 0:
            tail = Path(log).read_text(encoding="utf-8", errors="replace")[-400:]
            if "No such filter" in tail and "ass" in tail:
                raise RuntimeError("Your ffmpeg has no subtitle support (libass). Install the full ffmpeg build, for example 'full' from gyan.dev, then try again.")
            raise RuntimeError("ffmpeg failed: " + tail.strip())
        os.replace(tmp, out)
    finally:
        for f in (script, tmp):
            try:
                os.remove(f)
            except OSError:
                pass
        shutil.rmtree(workdir, ignore_errors=True)


# ---------- background worker ----------
def start_worker() -> None:
    global _started
    with _lock:
        if _started:
            return
        _started = True
    db.fail_stale_renders()
    threading.Thread(target=_loop, daemon=True).start()


def enqueue(clip_id: int) -> None:
    db.set_render(clip_id, "queued", 0, "")
    start_worker()
    _q.put(clip_id)


def _loop() -> None:
    while True:
        cid = _q.get()
        try:
            _render_clip(cid)
        except Exception as e:  # keep the worker alive whatever happens
            db.set_render(cid, "failed", 0, str(e)[:500])


def _render_clip(clip_id: int) -> None:
    c, edit = db.get_clip(clip_id), db.get_edit(clip_id)
    if not c or not edit:
        raise RuntimeError("Clip or saved edit not found")
    vdir = settings.video_dir(c["video_id"])
    src = next(iter(sorted(vdir.glob("original.*"))), None)
    if not src:
        raise RuntimeError("Original video file not found")
    name = f"clip_{c['rank']}_{clip_id}.mp4"
    db.set_render(clip_id, "rendering", 0, "")
    last = [0.0]

    def prog(pct: float) -> None:
        if pct - last[0] >= 1:
            last[0] = pct
            db.set_render(clip_id, "rendering", pct, "")

    cues = []
    if edit.get("captions_on", True):
        segs, _ = caps.load_segments(vdir)
        cues = caps.build_cues(segs, float(edit["start"]), float(edit["end"]))
    render_file(src, edit, vdir / "renders" / name, prog, cues, caps.find_font())
    db.set_render(clip_id, "done", 100, "", name)