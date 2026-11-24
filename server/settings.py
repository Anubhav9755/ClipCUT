"""Paths and config. Env vars let tests and deployments override them."""
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def cfg() -> dict:
    path = Path(os.environ.get("CLIPCUT_CONFIG", ROOT / "config.yaml"))
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def data_dir() -> Path:
    d = Path(os.environ.get("CLIPCUT_DATA", ROOT / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def video_dir(video_id: str) -> Path:
    d = data_dir() / "videos" / video_id
    d.mkdir(parents=True, exist_ok=True)
    return d
