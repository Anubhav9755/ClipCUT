"""One function for every AI provider. Returns parsed JSON."""
import json
import os
import re
import urllib.request


def _parse_json(text: str):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text)


def _claude(model: str, system: str, user: str, max_tokens: int) -> str:
    import anthropic  # reads ANTHROPIC_API_KEY
    msg = anthropic.Anthropic().messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in msg.content if b.type == "text")


def _gemini(model: str, system: str, user: str, max_tokens: int) -> str:
    key = os.environ["GEMINI_API_KEY"]
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": max_tokens},
    }
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])


def ask_json(provider: str, model: str, system: str, user: str, max_tokens: int = 4000):
    system += "\n\nRespond with valid JSON only. No preamble, no markdown fences."
    call = {"claude": _claude, "gemini": _gemini}[provider]
    last = None
    for _ in range(2):
        try:
            return _parse_json(call(model, system, user, max_tokens))
        except json.JSONDecodeError as e:
            last = e
    raise ValueError(f"{provider} did not return valid JSON: {last}")
