"""FFmpeg/ffprobe helpers: probe, proxy for the browser editor, audio, thumbnails, shot cuts."""
import json
import re
import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {p.stderr.strip()[-600:]}")
    return p.stdout


def probe(path: Path) -> dict:
    out = _run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    info = json.loads(out)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if v is None:
        raise RuntimeError("No video stream found in this file")
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "25/1").split("/")
    fps = float(num) / float(den) if float(den) else 25.0
    return {
        "duration": float(info["format"]["duration"]),
        "width": int(v["width"]), "height": int(v["height"]),
        "fps": round(fps, 3) or 25.0,
        "has_audio": any(s["codec_type"] == "audio" for s in info["streams"]),
    }


def make_proxy(src: Path, dst: Path, height: int, fps: float) -> None:
    """Small, seek-friendly copy for the browser. A keyframe every ~0.5s makes scrubbing fast;
    the final render always uses the original file, never this proxy."""
    gop = max(2, round(fps / 2))
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
          "-vf", f"scale=-2:'min(ih,{height})'",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
          "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0",
          "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(dst)])


def extract_audio(src: Path, dst: Path) -> None:
    """16 kHz mono WAV, the format speech models expect."""
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
          "-c:a", "pcm_s16le", str(dst)])


def extract_frames(proxy: Path, outdir: Path) -> int:
    """One thumbnail per second: frame_00001.jpg is the frame at t=0s, frame_00002.jpg at t=1s, ..."""
    outdir.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(proxy),
          "-vf", "fps=1,scale=320:-2", "-q:v", "5", str(outdir / "frame_%05d.jpg")])
    return len(list(outdir.glob("frame_*.jpg")))


def detect_shots(proxy: Path, threshold: float) -> list[float]:
    """Times (seconds) where the picture changes shot. Uses FFmpeg's scene score, no extra libraries."""
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(proxy),
           "-vf", f"select='gt(scene,{threshold})',metadata=print:file=-", "-an", "-f", "null", "-"]
    out = _run(cmd)
    return sorted({round(float(m), 2) for m in re.findall(r"pts_time:([0-9.]+)", out)})
