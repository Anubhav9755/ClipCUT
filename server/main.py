"""ClipCUT web server.  Run:  python run_server.py   then open http://localhost:8000"""
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from . import captions, db, jobs, render, settings, transcript, youtube

def _load_env() -> None:
    """Read <project>/.env into the environment, so the API key survives restarts and new terminals."""
    p = Path(__file__).resolve().parent.parent / ".env"
    if not p.exists():
        print(f"[ClipCUT] No .env file found at {p}")
        return
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:]
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and not v.endswith("...") and not os.environ.get(k):   # "sk-ant-..." is just the template
            os.environ[k] = v
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    print(f"[ClipCUT] Read {p} -> ANTHROPIC_API_KEY " + (f"found ({len(key)} characters, starts {key[:7]})" if key else "NOT found in it"))


_load_env()
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("\n*** WARNING: ANTHROPIC_API_KEY is not set. Clips will use the basic no-AI picker. "
          "Put it in a .env file next to run_server.py (ANTHROPIC_API_KEY=sk-ant-...) and restart. ***\n")

ALLOWED = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
ID = re.compile(r"[0-9a-f]{32}")
STATIC = Path(__file__).parent / "static"
security = HTTPBasic(auto_error=False)


def auth(creds: HTTPBasicCredentials | None = Depends(security)) -> None:
    """If CLIPCUT_PASSWORD is set, everything needs it (any username). The episodes are unreleased."""
    pw = os.environ.get("CLIPCUT_PASSWORD")
    if not pw:
        return
    if not creds or not secrets.compare_digest(creds.password.encode(), pw.encode()):
        raise HTTPException(401, "Password required", headers={"WWW-Authenticate": 'Basic realm="ClipCUT"'})


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = threading.Event()
    render.start_worker()
    if not os.environ.get("CLIPCUT_NO_WORKER"):
        threading.Thread(target=jobs.worker_loop, args=(stop,), daemon=True).start()
    yield
    stop.set()


app = FastAPI(title="ClipCUT", lifespan=lifespan, dependencies=[Depends(auth)])


def _vid(video_id: str) -> dict:
    if not ID.fullmatch(video_id):
        raise HTTPException(404, "Not found")
    v = db.get_video(video_id)
    if not v:
        raise HTTPException(404, "Not found")
    return v


def _detail(v: dict) -> dict:
    out = {k: v[k] for k in ("id", "filename", "status", "stage", "progress", "error", "created_at", "duration")}
    out["meta"] = json.loads(v["meta"] or "{}")
    out["clips"] = db.get_clips(v["id"]) if v["status"] == "done" else []
    return out


def range_response(path: Path, request: Request, media_type: str = "video/mp4") -> Response:
    """Serve a file with HTTP Range support (206 Partial Content). Browsers need this to seek in a video.
    Written by hand because older Starlette versions' FileResponse ignores the Range header."""
    size = path.stat().st_size
    headers = {"Accept-Ranges": "bytes", "Content-Type": media_type, "Cache-Control": "no-cache"}
    rng = request.headers.get("range")
    start, end, status = 0, size - 1, 200
    if rng:
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
        if not m or (m.group(1) == "" and m.group(2) == ""):
            return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{size}"})
        if m.group(1) == "":  # suffix range: the last N bytes
            start = max(0, size - int(m.group(2)))
        else:
            start = int(m.group(1))
            if m.group(2):
                end = min(int(m.group(2)), size - 1)
        if start >= size or start > end:
            return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{size}"})
        status = 206
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    length = end - start + 1
    headers["Content-Length"] = str(length)

    def body():
        with open(path, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                data = f.read(min(1 << 20, left))
                if not data:
                    break
                left -= len(data)
                yield data

    if request.method == "HEAD":
        return Response(status_code=status, headers=headers)
    return StreamingResponse(body(), status_code=status, headers=headers)


@app.get("/api/status")
def status():
    return {"ai_key": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/videos")
async def upload(file: UploadFile = File(...), script: UploadFile | None = File(None)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type. Use one of: {', '.join(sorted(ALLOWED))}")
    video_id = uuid.uuid4().hex
    vdir = settings.video_dir(video_id)
    with open(vdir / f"original{ext}", "wb") as f:
        while chunk := await file.read(1 << 20):  # stream to disk: episodes are large
            f.write(chunk)
    if script is not None and script.filename:
        text = (await script.read()).decode("utf-8-sig", errors="replace")
        if not transcript.parse_srt(text):
            raise HTTPException(400, "Could not read any subtitles from that .srt file")
        (vdir / "script.srt").write_text(text, encoding="utf-8")
    db.create_video(video_id, file.filename)
    return {"id": video_id}


@app.get("/api/videos")
def list_videos():
    return [_detail(v) for v in db.list_videos()]


@app.get("/api/videos/{video_id}")
def get_video(video_id: str):
    return _detail(_vid(video_id))


@app.post("/api/videos/{video_id}/rechoose")
def rechoose(video_id: str):
    """Pick clips again (e.g. after switching AI provider). Slow steps are cached and skipped."""
    _vid(video_id)
    db.requeue(video_id)
    return {"ok": True}


@app.api_route("/api/videos/{video_id}/proxy", methods=["GET", "HEAD"])
def proxy(video_id: str, request: Request):
    _vid(video_id)
    p = settings.video_dir(video_id) / "proxy.mp4"
    if not p.exists():
        raise HTTPException(404, "Preview not ready yet")
    return range_response(p, request)


@app.get("/api/videos/{video_id}/transcript")
def get_transcript(video_id: str):
    _vid(video_id)
    p = settings.video_dir(video_id) / "transcript.json"
    if not p.exists():
        raise HTTPException(404, "Transcript not ready yet")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/api/videos/{video_id}/frames/{n}")
def frame(video_id: str, n: int):
    """Thumbnail n (1-based): frame n is the picture at second n-1."""
    _vid(video_id)
    p = settings.video_dir(video_id) / "frames" / f"frame_{n:05d}.jpg"
    if not p.exists():
        raise HTTPException(404, "No such frame")
    return FileResponse(p, media_type="image/jpeg")


# ---------- clip editor: the edit decision list ----------
class Keyframe(BaseModel):
    t: float                      # seconds in the source video
    x: float = Field(ge=0, le=1)  # 9:16 window position: 0 = far left, 1 = far right
    mode: Literal["cut", "pan"]   # how we ARRIVE at this keyframe: jump, or glide from the previous one
    scene: bool = False           # True = auto-created at a scene start
    done: bool = False            # True = the editor has reviewed this scene


class EditIn(BaseModel):
    start: float
    end: float
    fps: float = 25
    keyframes: list[Keyframe] = Field(min_length=1, max_length=500)
    title: str = ""
    captions_on: bool = True
    approved: bool = False


@app.get("/api/clips/{clip_id}/edit")
def get_edit(clip_id: int):
    if not db.get_clip(clip_id):
        raise HTTPException(404, "Not found")
    e = db.get_edit(clip_id)
    c = db.get_clip(clip_id)
    if e:   # ignore an edit that belongs to a different clip (ids can be reused after "Choose clips again")
        same = abs(e.get("pad_start", c["pad_start"]) - c["pad_start"]) < 0.01 and abs(e.get("pad_end", c["pad_end"]) - c["pad_end"]) < 0.01
        inside = c["pad_start"] - 0.01 <= e["start"] < e["end"] <= c["pad_end"] + 0.01
        if not (same and inside):
            e = None
    return {"edit": e}


@app.put("/api/clips/{clip_id}/edit")
def put_edit(clip_id: int, body: EditIn):
    c = db.get_clip(clip_id)
    if not c:
        raise HTTPException(404, "Not found")
    if not (c["pad_start"] - 0.01 <= body.start < body.end <= c["pad_end"] + 0.01):
        raise HTTPException(400, "Trim must stay inside the padded range of the clip")
    data = body.model_dump()
    data["clip_id"] = clip_id
    data["video_id"] = c["video_id"]
    data["pad_start"], data["pad_end"] = c["pad_start"], c["pad_end"]
    db.save_edit(clip_id, data, body.approved)
    return {"ok": True}


@app.get("/api/clips/{clip_id}/shots")
def clip_shots(clip_id: int, threshold: float = 0.15, gap: float = 0.3):
    """Scene cuts (seconds in the source video) inside the clip's padded range. Cached per clip.
    Lower threshold = more cuts, higher = fewer."""
    c = db.get_clip(clip_id)
    if not c:
        raise HTTPException(404, "Not found")
    vdir = settings.video_dir(c["video_id"])
    src = vdir / "proxy.mp4"
    if not src.exists():
        raise HTTPException(404, "Preview not ready yet")
    a0, a1 = c["pad_start"], c["pad_end"]
    cache = vdir / f"shots_{clip_id}_{a0:.2f}_{a1:.2f}_{threshold}_{gap}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise HTTPException(500, "ffmpeg was not found on PATH")
    cmd = [ffmpeg, "-hide_banner", "-nostats", "-ss", f"{a0:.3f}", "-t", f"{a1 - a0:.3f}", "-i", str(src),
           "-an", "-vf", f"select=gt(scene\\,{threshold}),showinfo", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    except subprocess.TimeoutExpired:
        raise HTTPException(500, "Scene detection timed out")
    if r.returncode != 0:
        raise HTTPException(500, "ffmpeg failed: " + r.stderr[-300:])
    times = sorted(float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr))
    if times and max(times) > (a1 - a0) + 1:      # timestamps came back absolute, not relative to the seek
        times = [t - a0 for t in times]
    cuts = []
    for t in times:
        a = a0 + t
        if t < 0.4 or a1 - a < 0.4 or (cuts and a - cuts[-1] < gap):
            continue
        cuts.append(round(a, 3))
    out = {"cuts": cuts}
    cache.write_text(json.dumps(out))
    return out


# ---------- rendering ----------
@app.post("/api/clips/{clip_id}/render")
def start_render(clip_id: int):
    if not db.get_clip(clip_id):
        raise HTTPException(404, "Not found")
    edit = get_edit(clip_id)["edit"]
    if not edit or not edit.get("approved"):
        raise HTTPException(400, "Approve this clip in the editor first")
    r = db.get_render(clip_id)
    if r and r["status"] in ("queued", "rendering"):
        return r
    render.enqueue(clip_id)
    return db.get_render(clip_id)


@app.get("/api/clips/{clip_id}/render")
def render_status(clip_id: int):
    return db.get_render(clip_id) or {"status": ""}


@app.get("/api/clips/{clip_id}/render/file")
def render_file(clip_id: int, request: Request, download: int = 0):
    c, r = db.get_clip(clip_id), db.get_render(clip_id)
    if not c or not r or r["status"] not in ("done", "stale") or not r["output"]:
        raise HTTPException(404, "No rendered file yet")
    p = settings.video_dir(c["video_id"]) / "renders" / r["output"]
    if not p.exists():
        raise HTTPException(404, "Rendered file is missing")
    if download:
        return FileResponse(p, media_type="video/mp4", filename=f"clip_{c['rank']}.mp4")
    return range_response(p, request)


# ---------- YouTube ----------
class MetaIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=5000)
    tags: list[str] = []
    privacy: Literal["private", "unlisted", "public"] = "private"


class GenIn(BaseModel):
    template: str | None = None


@app.get("/api/youtube/status")
def yt_status():
    return youtube.status()


@app.get("/api/youtube/connect")
def yt_connect(request: Request):
    if not youtube.libs_ok():
        raise HTTPException(400, "Run: pip install google-api-python-client google-auth-oauthlib")
    if not youtube.secret_path().exists():
        raise HTTPException(400, f"client_secret.json not found at {youtube.secret_path()}")
    return RedirectResponse(youtube.auth_url(str(request.base_url) + "api/youtube/callback"))


@app.get("/api/youtube/callback")
def yt_callback(request: Request, state: str = "", error: str = ""):
    if error:
        raise HTTPException(400, f"Google said: {error}")
    try:
        youtube.finish_auth(state, str(request.url))
    except Exception as e:
        raise HTTPException(400, f"Could not connect YouTube: {e}")
    return RedirectResponse("/")


@app.get("/api/clips/{clip_id}/captions")
def clip_captions(clip_id: int):
    """Caption cues for the clip's padded range, exactly as the renderer will burn them in (used by the editor preview)."""
    c = db.get_clip(clip_id)
    if not c:
        raise HTTPException(404, "Not found")
    segs, source = captions.load_segments(settings.video_dir(c["video_id"]))
    return {"source": source, "cues": captions.build_cues(segs, c["pad_start"], c["pad_end"])}


@app.get("/api/settings/youtube-template")
def get_template():
    return {"template": db.get_kv("yt_template") or youtube.DEFAULT_TEMPLATE}


@app.post("/api/clips/{clip_id}/youtube/metadata")
def yt_metadata(clip_id: int, body: GenIn):
    c = db.get_clip(clip_id)
    edit = db.get_edit(clip_id)
    if not c or not edit:
        raise HTTPException(404, "Not found")
    if body.template is not None and body.template.strip():
        db.set_kv("yt_template", body.template)
    template = body.template or db.get_kv("yt_template") or youtube.DEFAULT_TEMPLATE
    try:
        return youtube.generate_metadata(c, edit, template)
    except Exception as e:
        raise HTTPException(500, f"Claude could not write the text: {e}")


@app.post("/api/clips/{clip_id}/youtube/upload")
def yt_upload(clip_id: int, body: MetaIn):
    c, r = db.get_clip(clip_id), db.get_render(clip_id)
    if not c:
        raise HTTPException(404, "Not found")
    if not r or r["status"] != "done" or not r["output"]:
        raise HTTPException(400, "Render the clip first (or render it again if you edited it)")
    p = db.get_post(clip_id)
    if p and p["status"] == "uploading":
        raise HTTPException(400, "Already uploading")
    if p and p["status"] == "done":
        raise HTTPException(400, f"Already posted: {p['url']}")
    if not youtube.status()["connected"]:
        raise HTTPException(400, "YouTube is not connected")
    f = settings.video_dir(c["video_id"]) / "renders" / r["output"]
    if not f.exists():
        raise HTTPException(404, "Rendered file is missing")
    meta = body.model_dump()
    meta["title"] = meta["title"].replace("<", "").replace(">", "")
    meta["description"] = meta["description"].replace("<", "").replace(">", "")
    youtube.start_upload(clip_id, f, meta)
    return {"ok": True}