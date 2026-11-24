"""Step 1: speech -> text with timestamps (faster-whisper, free)."""
from pathlib import Path


def run(video: Path, cfg: dict) -> dict:
    """Returns {"segments": [...], "cues": [...]}.
    segments = sentence-ish chunks (used by the AI to pick clips)
    cues     = short subtitle-sized chunks (used for on-screen subtitles)
    """
    from faster_whisper import WhisperModel  # imported here so other steps work without it

    w = cfg["whisper"]
    model = WhisperModel(w["model"], device=w["device"], compute_type=w["compute_type"])
    lang = cfg.get("source_language")
    raw_segments, _info = model.transcribe(
        str(video), language=lang, word_timestamps=True, vad_filter=True
    )

    segments, words = [], []
    for s in raw_segments:
        text = s.text.strip()
        if not text:
            continue
        segments.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": text})
        for wd in s.words or []:
            words.append({"start": wd.start, "end": wd.end, "text": wd.word.strip()})

    s_cfg = cfg["subtitles"]
    cues = build_cues(words, s_cfg["max_chars_per_cue"], s_cfg["max_seconds_per_cue"])
    return {"segments": segments, "cues": cues}


def build_cues(words, max_chars, max_seconds):
    """Group words into short, readable subtitle cues."""
    cues, cur = [], []

    def flush():
        if cur:
            cues.append({
                "start": round(cur[0]["start"], 2),
                "end": round(cur[-1]["end"], 2),
                "text": " ".join(w["text"] for w in cur),
            })
            cur.clear()

    for w in words:
        if cur:
            text_len = len(" ".join(x["text"] for x in cur)) + 1 + len(w["text"])
            too_long = text_len > max_chars
            too_slow = (w["end"] - cur[0]["start"]) > max_seconds
            gap = (w["start"] - cur[-1]["end"]) > 0.8
            if too_long or too_slow or gap:
                flush()
        cur.append(w)
        if w["text"].endswith((".", "?", "!", "।")):
            flush()
    flush()
    return cues
