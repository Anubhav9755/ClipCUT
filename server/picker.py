"""Chooses the best moments: AI proposes, code validates, a no-AI fallback fills gaps."""
from . import llm

DEFAULT_SERIES = "an animated Hindi-language series for families"

_SYSTEM_T = """You are the social media editor for {series}.
The dialogue is in Hindi (Devanagari). From one episode you choose the moments that make the best
short clips for Instagram Reels, YouTube Shorts, TikTok and Facebook.

A great clip:
- starts at the beginning of a sentence and ends at the end of one (never mid-sentence)
- makes sense with no context: a clear mini-story, a punchline, a clever comeback, or a cliffhanger
- hooks the viewer in the first 3 seconds
- does not spoil the ending of the episode, unless it is a teaser that stops on a cliffhanger
- is funny, surprising, emotional or clever: moments with loud audio peaks often are

Mark each clip "short" (self-contained moment) or "promo" (teaser that makes people watch the episode)."""

SYSTEM = _SYSTEM_T.format(series=DEFAULT_SERIES)  # kept for older callers; pick() uses system_prompt(a)


def system_prompt(a: dict) -> str:
    return _SYSTEM_T.format(series=a.get("series_context") or DEFAULT_SERIES)


def build_prompt(transcript: dict, shots: list[float], audio: dict, duration: float, a: dict) -> str:
    unsure = a.get("caption_conf_threshold", 0.75)
    lines = "\n".join(
        f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" + (" (unsure)" if s.get("conf", 1.0) < unsure else "")
        for s in transcript["segments"])
    note = ("Lines marked (unsure) came from speech recognition and may be wrong or in the wrong script; "
            "do not judge a moment by their wording alone, also use timing, shot changes and loud audio moments.\n\n"
            if transcript.get("source") != "srt" else "")
    shots_txt = ", ".join(f"{t:.1f}" for t in shots) or "none detected"
    peaks_txt = ", ".join(f"{p['t']:.1f}" for p in audio["peaks"]) or "none"
    return f"""Episode length: {duration:.0f} seconds.

{note}Dialogue with timestamps (seconds):
{lines}

Shot changes (seconds): {shots_txt}
Loud audio moments (seconds): {peaks_txt}

Pick the {a['clips_per_video']} best clips, each between {a['min_seconds']} and {a['max_seconds']} seconds long (the end minus the start must be in that range).
Clips must not overlap. Use start and end times that match sentence boundaries above.

Return a JSON list, best first:
[{{"start": 12.4, "end": 41.0, "score": 9.2, "type": "short",
   "title": "short title in Hindi (Devanagari)", "reason": "one sentence in English: why this works"}}]"""


def _nearest(t: float, candidates: list[float], tol: float) -> float | None:
    if not candidates:
        return None
    best = min(candidates, key=lambda c: abs(c - t))
    return best if abs(best - t) <= tol else None


def _overlaps(s: float, e: float, kept: list[dict]) -> bool:
    return any(s < k["end"] and e > k["start"] for k in kept)


def validate(raw, segments: list[dict], shots: list[float], duration: float, a: dict) -> list[dict]:
    """Never trust the model blindly: clamp, snap to sentence/shot boundaries, enforce length, drop overlaps."""
    if not isinstance(raw, list):
        return []
    tol, lo, hi = a["snap_tolerance_seconds"], a["min_seconds"], a["max_seconds"]
    starts = [s["start"] for s in segments]
    ends = [s["end"] for s in segments]

    def score_of(x):
        try:
            return float(x.get("score") or 0)
        except (TypeError, ValueError, AttributeError):
            return 0.0

    kept = []
    for item in sorted((x for x in raw if isinstance(x, dict)), key=score_of, reverse=True):
        try:
            s, e = float(item["start"]), float(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        s, e = max(0.0, s), min(duration, e)
        if e <= s:
            continue
        for snap_to in (starts, shots):          # prefer a sentence start, else a shot change
            hit = _nearest(s, snap_to, tol)
            if hit is not None:
                s = hit
                break
        for snap_to in (ends, shots):            # prefer a sentence end, else a shot change
            hit = _nearest(e, snap_to, tol)
            if hit is not None:
                e = hit
                break
        if e - s > hi:
            fits = [x for x in ends if s + lo <= x <= s + hi]
            e = max(fits) if fits else s + hi
        if e - s < lo or _overlaps(s, e, kept):
            continue
        kept.append({
            "start": round(s, 2), "end": round(e, 2), "score": round(score_of(item), 1),
            "type": item.get("type", "short"), "title": str(item.get("title", "")).strip() or "Untitled",
            "reason": str(item.get("reason", "")).strip(), "source": item.get("source", "ai"),
        })
    return kept


def heuristic(segments: list[dict], audio: dict, duration: float, a: dict, short: bool = False) -> list[dict]:
    """No-AI picker: busy dialogue + loud moments + a punchy ending. Used for testing and as a fallback."""
    if not segments:
        return []
    lo, hi = a["min_seconds"], a["max_seconds"]
    if short:  # second pass: shorter windows so they fit into the gaps left by the first pass
        hi = min(hi, lo * 1.5)
    target = min(hi, (lo + hi) / 2)
    z, w = audio.get("z", []), audio.get("window", 0.5)
    words = lambda seg: len(seg["text"].split())  # noqa: E731
    mean_density = max(sum(words(s) for s in segments) / max(duration, 1.0), 1e-6)
    cands = []
    for seg in segments:
        s = seg["start"]
        ends = [x for x in segments if s + lo <= x["end"] <= s + hi]
        if not ends:
            continue
        last = min(ends, key=lambda x: abs(x["end"] - (s + target)))
        e = last["end"]
        inside = [x for x in segments if x["start"] >= s and x["end"] <= e]
        density = sum(words(x) for x in inside) / (e - s) / mean_density
        zz = z[int(s / w): int(e / w)]
        loud = max(-1.0, min(3.0, sum(zz) / len(zz))) if zz else 0.0
        peaks = sum(1 for p in audio.get("peaks", []) if s <= p["t"] <= e)
        punch = 0.5 if last["text"].rstrip().endswith(("?", "!")) else 0.0
        cands.append((density + 0.8 * loud + 0.3 * peaks + punch, s, e, inside[0]["text"]))
    if not cands:
        return []
    top = max(c[0] for c in cands) or 1.0
    return [{"start": s, "end": e, "score": 10 * sc / top if top > 0 else 0, "type": "short",
             "title": text[:40], "reason": "Busy dialogue and loud moments (no-AI picker)",
             "source": "heuristic"}
            for sc, s, e, text in sorted(cands, reverse=True)]


def _finish(clips: list[dict], segments: list[dict], duration: float, transcript_source: str, a: dict) -> list[dict]:
    out = []
    for rank, c in enumerate(clips, 1):
        c = dict(c, rank=rank)
        c["pad_start"] = round(max(0.0, c["start"] - a["pad_seconds"]), 2)
        c["pad_end"] = round(min(duration, c["end"] + a["pad_seconds"]), 2)
        inside = [s for s in segments if s["end"] > c["pad_start"] and s["start"] < c["pad_end"]]
        total = sum(s["end"] - s["start"] for s in inside)
        conf = sum(s.get("conf", 1.0) * (s["end"] - s["start"]) for s in inside) / total if total else 0.0
        c["caption_conf"] = round(conf, 2)
        verified = transcript_source == "srt"
        c["caption_gate"] = "ok" if (verified or conf >= a["caption_conf_threshold"]) and inside else "off"
        out.append(c)
    return out


def pick(transcript: dict, shots: list[float], audio: dict, duration: float, cfg: dict):
    a = cfg["analysis"]
    n, provider = a["clips_per_video"], a["provider"]
    segs = transcript["segments"]
    info = {"provider_requested": provider, "provider_used": provider, "warning": None}
    clips: list[dict] = []

    if not segs:
        info.update(provider_used="none", warning="No dialogue found, so there was nothing to pick from.")
        return [], info

    if provider in ("claude", "gemini"):
        try:
            raw = llm.ask_json(provider, a[f"{provider}_model"], system_prompt(a),
                               build_prompt(transcript, shots, audio, duration, a))
            clips = validate([dict(x, source=provider) for x in raw if isinstance(x, dict)]
                             if isinstance(raw, list) else raw, segs, shots, duration, a)[:n]
        except Exception as e:  # no key, no network, bad JSON...: never leave the editor empty-handed
            info.update(provider_used="heuristic", warning=f"{provider} failed ({e}); used the no-AI picker instead.")
    if len(clips) < n:
        if provider in ("claude", "gemini") and info["provider_used"] == provider:
            info["warning"] = f"{provider} gave {len(clips)} usable clips; the rest were filled by the no-AI picker."
        for short in (False, True):
            for h in validate(heuristic(segs, audio, duration, a, short), segs, shots, duration, a):
                if len(clips) >= n:
                    break
                if not _overlaps(h["start"], h["end"], clips):
                    clips.append(dict(h, source="heuristic"))
    return _finish(clips, segs, duration, transcript["source"], a), info