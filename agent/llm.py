"""Thin wrapper around the Claude API that always returns parsed JSON."""
import json
import re

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic  # reads ANTHROPIC_API_KEY from the environment
        _client = anthropic.Anthropic()
    return _client


def _parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)


def ask_json(model: str, system: str, user: str, max_tokens: int = 4000):
    """Send a prompt, expect JSON back. Retries once if the JSON is malformed."""
    client = _get_client()
    last_err = None
    for _ in range(2):
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system + "\n\nRespond with valid JSON only. No preamble, no markdown fences.",
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        try:
            return _parse_json(text)
        except json.JSONDecodeError as e:
            last_err = e
    raise ValueError(f"Model did not return valid JSON: {last_err}")
