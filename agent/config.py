from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent


def load(path: str | None = None) -> dict:
    p = Path(path) if path else ROOT / "config.yaml"
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)
