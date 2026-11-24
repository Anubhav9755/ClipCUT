"""Step 3: subtitles + captions in every language, with a safety check on the output."""
from . import llm

SYSTEM = """You localize subtitles and social media posts for "Tenali Rama", a 3D animated series
for families. Your work is read by native speakers, so it must sound natural, not literal.

Rules:
- Keep the humor and the wit. Adapt idioms; do not translate word-for-word.
- Subtitles: exactly one output line per input line, same order. Max ~42 characters each.
- Never translate or change these names/terms: {keep_terms}
- If the target language is the same as the source, keep the dialogue as is.
- Captions are friendly and short (1-2 sentences, up to 2 emojis), ending with a hook to watch more.
- Hashtags: 5-8, mix of English and the target language, no spaces inside a tag, no leading '#'.
- Keep it family-friendly."""


def make_variant(cues: list[dict], clip: dict, lang: str, cfg: dict) -> dict:
    """Returns {"title", "caption", "hashtags", "subtitles": [..], "needs_review": bool}."""
    system = SYSTEM.format(keep_terms=", ".join(cfg["keep_terms"]))
    numbered = "\n".join(f"{i + 1}. {c['text']}" for i, c in enumerate(cues))
    user = f"""Source language: {cfg['source_language']}
Target language: {lang}
Clip type: {clip['type']}  |  Working title: {clip['title']}  |  Why it works: {clip['reason']}

Dialogue lines to translate ({len(cues)} lines):
{numbered}

Return JSON:
{{"title": "title for the post in {lang}", "caption": "...", "hashtags": ["..."],
  "subtitles": [{len(cues)} strings, one per dialogue line]}}"""

    for attempt in range(2):
        out = llm.ask_json(cfg["claude_model"], system, user)
        subs = out.get("subtitles", [])
        if isinstance(subs, list) and len(subs) == len(cues):
            return {
                "title": str(out.get("title", clip["title"])),
                "caption": str(out.get("caption", "")),
                "hashtags": [str(h).lstrip("#") for h in out.get("hashtags", [])],
                "subtitles": [str(s) for s in subs],
                "needs_review": False,
            }
    # Model kept returning the wrong number of lines: fall back to source text and flag it.
    return {
        "title": clip["title"], "caption": "", "hashtags": [],
        "subtitles": [c["text"] for c in cues], "needs_review": True,
    }


def cues_for_clip(all_cues: list[dict], start: float, end: float) -> list[dict]:
    """Cues inside [start, end], with times shifted so the clip starts at 0."""
    out = []
    for c in all_cues:
        if c["end"] <= start or c["start"] >= end:
            continue
        out.append({
            "start": round(max(c["start"], start) - start, 2),
            "end": round(min(c["end"], end) - start, 2),
            "text": c["text"],
        })
    return out


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: list[dict], texts: list[str]) -> str:
    blocks = []
    for i, (c, text) in enumerate(zip(cues, texts), 1):
        blocks.append(f"{i}\n{_ts(c['start'])} --> {_ts(c['end'])}\n{text}\n")
    return "\n".join(blocks)
