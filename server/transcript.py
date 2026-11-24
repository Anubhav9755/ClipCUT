"""Transcript sources: an uploaded SRT/script timing file (best), or speech recognition."""
import math
import re
from pathlib import Path

_TS = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def _secs(h, m, s, ms) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000


def parse_srt(text: str) -> list[dict]:
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    segs = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            m = _TS.search(line)
            if m:
                g = m.groups()
                body = re.sub(r"<[^>]+>", "", " ".join(lines[i + 1:])).strip()
                if body:
                    segs.append({"start": round(_secs(*g[:4]), 2), "end": round(_secs(*g[4:]), 2),
                                 "text": body, "conf": 1.0})
                break
    return segs


def from_srt(path: Path) -> dict:
    segs = parse_srt(path.read_text(encoding="utf-8-sig"))
    return {"source": "srt", "language": None, "segments": segs}


def from_whisper(audio: Path, asr_cfg: dict) -> dict:
    """Speech recognition with faster-whisper. conf = per-segment confidence (0-1)."""
    from faster_whisper import WhisperModel  # imported here so the server runs without it

    model = WhisperModel(asr_cfg["model"], device=asr_cfg.get("device", "auto"),
                         compute_type=asr_cfg.get("compute_type", "int8"))
    raw, info = model.transcribe(str(audio), language=asr_cfg.get("language"), vad_filter=True,
                                 beam_size=5, condition_on_previous_text=False,
                                 initial_prompt=asr_cfg.get("initial_prompt") or None)
    segs = []
    for s in raw:
        text = s.text.strip()
        if text:
            segs.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": text,
                         "conf": round(min(1.0, math.exp(s.avg_logprob)), 3)})
    return {"source": "whisper", "language": info.language, "segments": segs}