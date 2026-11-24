"""Burned-in Hindi captions: turn transcript lines into short caption cues and an .ass subtitle file for ffmpeg/libass."""
import json
import re
import shutil
from pathlib import Path

MAX_CHARS = 30          # per caption cue (two short lines at most on a 1080-wide frame)
MIN_CUE = 0.5           # seconds
FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"


def load_segments(video_dir: Path) -> tuple[list[dict], str]:
    p = video_dir / "transcript.json"
    if not p.exists():
        return [], ""
    t = json.loads(p.read_text(encoding="utf-8"))
    segs = t.get("segments", [])
    out = []
    for i, s in enumerate(segs):
        start = float(s["start"])
        end = s.get("end")
        if end is None:
            end = segs[i + 1]["start"] if i + 1 < len(segs) else start + 3
        end = min(float(end), start + 8)                 # no caption stays on screen for ages
        text = re.sub(r"\s+", " ", str(s.get("text", ""))).strip()
        if text and end > start:
            out.append({"start": start, "end": end, "text": text, "conf": s.get("conf")})
    return out, t.get("source", "")


def _chunks(text: str) -> list[str]:
    words, out, cur = text.split(" "), [], ""
    for w in words:
        while len(w) > MAX_CHARS:                        # a very long word with no spaces
            if cur:
                out.append(cur); cur = ""
            out.append(w[:MAX_CHARS]); w = w[MAX_CHARS:]
        if cur and len(cur) + 1 + len(w) > MAX_CHARS:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    if len(out) > 1 and len(out[-1]) < 10 and len(out[-2]) + 1 + len(out[-1]) <= MAX_CHARS + 10:
        out[-2:] = [out[-2] + " " + out[-1]]            # don't flash a one-word cue at the end
    return out


def build_cues(segments: list[dict], a: float, b: float) -> list[dict]:
    """Caption cues (absolute source times) that fall inside [a, b]. Long lines are split into short cues,
    each shown for a share of the line's time proportional to its length."""
    cues = []
    for s in segments:
        if s["end"] <= a or s["start"] >= b:
            continue
        parts = _chunks(s["text"])
        total = sum(len(p) for p in parts) or 1
        t = s["start"]
        for p in parts:
            d = (s["end"] - s["start"]) * len(p) / total
            c0, c1 = t, t + max(d, MIN_CUE)
            t += d
            c0, c1 = max(c0, a), min(c1, b)
            if c1 - c0 >= 0.15:
                cues.append({"start": round(c0, 3), "end": round(c1, 3), "text": p})
    for x, y in zip(cues, cues[1:]):                     # never overlap on screen
        if x["end"] > y["start"]:
            x["end"] = y["start"]
    return [c for c in cues if c["end"] - c["start"] >= 0.15]


def find_font() -> Path | None:
    """The Noto Sans Devanagari file inside the project's fonts folder (Bold if present)."""
    if not FONTS_DIR.exists():
        return None
    files = [f for f in FONTS_DIR.rglob("*") if f.suffix.lower() in (".ttf", ".otf") and "devanagari" in f.name.lower()]
    if not files:
        return None
    pref = ["notosansdevanagari-bold", "notosansdevanagari-semibold", "notosansdevanagari-extrabold", "notosansdevanagari-medium", "notosansdevanagari-regular"]
    by = {f.stem.lower(): f for f in files}
    for name in pref:
        if name in by:
            return by[name]
    plain = [f for f in files if "[" not in f.name and "variable" not in f.name.lower() and "_" not in f.stem]
    return (plain or files)[0]


def _font_names(font: Path) -> tuple[str, bool]:
    """(family name, is bold) as libass will see them."""
    try:
        from fontTools.ttLib import TTFont
        n = TTFont(str(font), fontNumber=0)["name"]
        fam, sty = n.getDebugName(1), n.getDebugName(2) or ""
        if fam:
            return fam, "bold" in sty.lower()
    except Exception:
        pass
    return "Noto Sans Devanagari", "bold" in font.stem.lower()


def _t(sec: float) -> str:
    cs = int(round(sec * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def write_ass(cues: list[dict], shift: float, workdir: Path, font: Path | None) -> None:
    """Write cap.ass (and a fonts/ folder with the one font) into workdir. Times are shifted so the clip starts at 0."""
    family, bold = "Noto Sans Devanagari", True
    if font:
        (workdir / "fonts").mkdir(exist_ok=True)
        shutil.copy(font, workdir / "fonts" / font.name)
        family, bold = _font_names(font)
    head = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Cap,{family},76,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,{-1 if bold else 0},0,0,0,100,100,0,0,1,7,0,2,90,90,360,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    lines = []
    for c in cues:
        text = c["text"].replace("\\", "").replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{_t(c['start'] - shift)},{_t(c['end'] - shift)},Cap,,0,0,0,,{text}")
    (workdir / "cap.ass").write_text(head + "\n".join(lines) + "\n", encoding="utf-8")