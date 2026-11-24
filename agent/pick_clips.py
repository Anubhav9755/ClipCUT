"""Step 2: the AI picks the best moments for shorts and promos."""
import subprocess

from . import llm

SYSTEM = """You are the social media editor for "Tenali Rama", a 3D animated series based on the
witty court jester of Vijayanagara. You choose the moments from an episode that make the best
short clips for Instagram Reels, TikTok, YouTube Shorts, Facebook and X.

A great clip:
- starts at the beginning of a sentence and ends at the end of one (never mid-sentence)
- works with no context: a clear mini-story, a punchline, a clever comeback, or a cliffhanger
- hooks in the first 3 seconds
- does NOT give away the ending of the episode (unless it is a teaser that ends on a cliffhanger)

Mark each clip type "short" (self-contained funny/clever moment) or "promo" (teaser that makes
people want to watch the full episode)."""


def probe_duration(video) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out.strip())


def detect_scenes(video) -> list[float]:
    """Scene-change timestamps in seconds. Returns [] if PySceneDetect isn't installed."""
    try:
        from scenedetect import detect, ContentDetector
    except ImportError:
        return []
    scenes = detect(str(video), ContentDetector())
    return [s[0].get_seconds() for s in scenes[1:]]


def _mmss(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def _snap(t: float, scene_cuts: list[float], tolerance: float) -> float:
    if not scene_cuts:
        return t
    nearest = min(scene_cuts, key=lambda c: abs(c - t))
    return nearest if abs(nearest - t) <= tolerance else t


def pick(segments: list[dict], scene_cuts: list[float], cfg: dict, duration: float) -> list[dict]:
    c = cfg["clips"]
    transcript = "\n".join(f"[{s['start']:.2f}-{s['end']:.2f}] {s['text']}" for s in segments)
    user = f"""Episode transcript with timestamps in seconds:

{transcript}

Pick up to {c['per_episode']} clips, each between {c['min_seconds']} and {c['max_seconds']} seconds long.
Clips must not overlap. Use start/end times that match the sentence boundaries above.

Return a JSON list, best clip first:
[{{"start": 12.4, "end": 41.0, "type": "short", "title": "short working title", "reason": "why this works"}}]"""

    raw = llm.ask_json(cfg["claude_model"], SYSTEM, user)
    return validate(raw, scene_cuts, cfg, duration)


def validate(raw: list[dict], scene_cuts: list[float], cfg: dict, duration: float) -> list[dict]:
    """Never trust the model blindly: clamp, snap, enforce length, drop overlaps."""
    c = cfg["clips"]
    good = []
    for item in raw:
        try:
            start, end = float(item["start"]), float(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        start = _snap(max(0.0, start), scene_cuts, c["snap_to_scene_seconds"])
        end = _snap(min(duration, end), scene_cuts, c["snap_to_scene_seconds"])
        length = end - start
        if length > c["max_seconds"]:
            end = start + c["max_seconds"]
        elif length < c["min_seconds"]:
            continue
        if any(start < g["end"] and end > g["start"] for g in good):
            continue  # overlaps a clip we already kept
        good.append({
            "start": round(start, 2), "end": round(end, 2),
            "type": item.get("type", "short"),
            "title": str(item.get("title", "Untitled")),
            "reason": str(item.get("reason", "")),
        })
    return good[: c["per_episode"]]
