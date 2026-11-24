"""YouTube posting: Google login, Claude-written title/description/tags, background upload.

Setup (once): see the Product Guide, section 7. You need client_secret.json next to run_server.py and
    pip install google-api-python-client google-auth-oauthlib
The login token is stored in data/youtube_token.json. Nothing here runs until you press "Connect YouTube".
"""
import json
import os
import re
import threading
from pathlib import Path

from . import captions, db, llm, settings

ROOT = Path(__file__).resolve().parent.parent
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
MODEL = os.environ.get("CLIPCUT_MODEL", "claude-sonnet-5-5")

DEFAULT_TEMPLATE = """{one-line hook about this moment}

{2-3 lines about what happens in this clip, without spoiling the whole episode}

Watch the full episode: {link to the full episode}
Subscribe for more!

#Shorts #Animation #Kids"""

_pending: dict = {}          # login in progress: state -> Flow (it holds the PKCE secret until Google calls back)
_lock = threading.Lock()


# ---------- login ----------
def secret_path() -> Path:
    return ROOT / "client_secret.json"


def token_path() -> Path:
    return settings.data_dir() / "youtube_token.json"


def libs_ok() -> bool:
    try:
        import google.oauth2.credentials  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
        import googleapiclient.discovery  # noqa: F401
        return True
    except ImportError:
        return False


def status() -> dict:
    """libs: packages installed. configured: client_secret.json present. connected: logged in."""
    connected = False
    if libs_ok() and token_path().exists():
        try:
            connected = bool(json.loads(token_path().read_text(encoding="utf-8")).get("refresh_token"))
        except (OSError, ValueError):
            connected = False
    return {"libs": libs_ok(), "configured": secret_path().exists(), "connected": connected}


def _relax_oauthlib() -> None:
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"      # the login callback is http://localhost
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"       # don't fail if Google reports the scope slightly differently


def auth_url(redirect_uri: str) -> str:
    from google_auth_oauthlib.flow import Flow
    _relax_oauthlib()
    flow = Flow.from_client_secrets_file(str(secret_path()), scopes=SCOPES, redirect_uri=redirect_uri)
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    with _lock:
        _pending[state] = flow
    return url


def finish_auth(state: str, response_url: str) -> None:
    _relax_oauthlib()
    with _lock:
        flow = _pending.pop(state, None)
    if flow is None:
        raise ValueError("This login link expired or was already used. Press Connect YouTube again.")
    flow.fetch_token(authorization_response=response_url)
    token_path().write_text(flow.credentials.to_json(), encoding="utf-8")


def _service():
    """An authorised YouTube client (refreshes the token if needed)."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    if not token_path().exists():
        raise RuntimeError("YouTube is not connected")
    creds = Credentials.from_authorized_user_file(str(token_path()), SCOPES)
    if not creds.valid:
        creds.refresh(Request())
        token_path().write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


# ---------- title / description / tags written by Claude ----------
SYSTEM = """You write YouTube Shorts metadata for a family animated series.
Return JSON: {"title": str, "description": str, "tags": [str]}.

Title: at most 70 characters, curiosity-driven, no clickbait lies, no emoji spam. Write it in the language of the dialogue
(Hindi in Devanagari if the dialogue is Hindi).
Description: follow the user's TEMPLATE. Keep every fixed line, link and hashtag of the template exactly as written, and
replace each {placeholder} with fitting text based on the clip. Do not invent facts that are not in the dialogue or the reason.
Always include the hashtag #Shorts.
Tags: 8 to 15 short tags (Hindi and English mix is fine), without the # sign."""


def _dialogue(clip: dict, edit: dict, limit: int = 3500) -> str:
    segs, _ = captions.load_segments(settings.video_dir(clip["video_id"]))
    a, b = float(edit.get("start", clip["start"])), float(edit.get("end", clip["end"]))
    text = " ".join(s["text"] for s in segs if s["end"] > a and s["start"] < b)
    return text[:limit]


def _clean_title(t: str) -> str:
    t = re.sub(r"[<>]", "", str(t)).strip().strip('"').strip()
    if len(t) > 70:
        cut = t[:70].rsplit(" ", 1)[0]
        t = cut if len(cut) >= 30 else t[:70]
    return t or "New clip"


def generate_metadata(clip: dict, edit: dict, template: str) -> dict:
    user = (f"TEMPLATE:\n{template}\n\n"
            f"Why this clip was picked: {clip.get('reason', '')}\n"
            f"Working title: {edit.get('title') or clip.get('title', '')}\n\n"
            f"Dialogue in this clip:\n{_dialogue(clip, edit)}")
    out = llm.ask_json("claude", MODEL, SYSTEM, user, max_tokens=1500)
    if not isinstance(out, dict):
        raise ValueError("Claude returned an unexpected answer")
    desc = re.sub(r"[<>]", "", str(out.get("description", ""))).strip()
    if "#shorts" not in desc.lower():
        desc += "\n\n#Shorts"
    tags, total = [], 0
    for t in out.get("tags", []):
        t = re.sub(r"[<>#,]", "", str(t)).strip()
        if t and t.lower() not in (x.lower() for x in tags) and total + len(t) + 1 <= 450:   # YouTube caps all tags at ~500 chars
            tags.append(t)
            total += len(t) + 1
    return {"title": _clean_title(out.get("title", "")), "description": desc[:5000], "tags": tags[:15]}


# ---------- upload (background thread) ----------
def _friendly(e: Exception) -> str:
    try:
        from googleapiclient.errors import HttpError
        if isinstance(e, HttpError):
            detail = json.loads(e.content.decode("utf-8", "replace")).get("error", {})
            reasons = {x.get("reason") for x in detail.get("errors", [])}
            if "quotaExceeded" in reasons or "uploadLimitExceeded" in reasons:
                return "YouTube's daily upload limit was reached. Try again tomorrow."
            return detail.get("message") or str(e)
    except Exception:
        pass
    return str(e)


def start_upload(clip_id: int, path: Path, meta: dict) -> None:
    db.set_post(clip_id, "uploading", 0, "")
    threading.Thread(target=_upload, args=(clip_id, Path(path), dict(meta)), daemon=True).start()


def _upload(clip_id: int, path: Path, meta: dict) -> None:
    try:
        from googleapiclient.http import MediaFileUpload
        yt = _service()
        body = {
            "snippet": {"title": meta["title"], "description": meta["description"], "tags": meta.get("tags", []),
                        "categoryId": "1"},     # Film & Animation. "Made for kids" is deliberately NOT set: it follows your channel's setting
            "status": {"privacyStatus": meta.get("privacy", "private")},
        }
        media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp, last = None, -1
        while resp is None:
            st, resp = req.next_chunk()
            if st is not None and int(st.progress() * 100) != last:
                last = int(st.progress() * 100)
                db.set_post(clip_id, "uploading", last, "")
        db.set_post(clip_id, "done", 100, "", f"https://www.youtube.com/shorts/{resp['id']}")
    except Exception as e:      # the page shows this message next to the clip
        db.set_post(clip_id, "failed", 0, _friendly(e)[:400])