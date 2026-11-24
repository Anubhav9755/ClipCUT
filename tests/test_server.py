"""Server tests: real FFmpeg on a synthetic 3-minute video, real SQLite, fake AI. Run: pytest tests/test_server.py -q"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = Path(tempfile.mkdtemp())
os.environ["CLIPCUT_DATA"] = str(TMP / "data")
os.environ["CLIPCUT_NO_WORKER"] = "1"
os.environ["CLIPCUT_CONFIG"] = str(TMP / "config.yaml")
os.environ.pop("CLIPCUT_PASSWORD", None)

from fastapi.testclient import TestClient  # noqa: E402
from server import db, jobs, llm, main, media, settings  # noqa: E402


def set_provider(provider: str) -> None:
    cfg = yaml.safe_load(open(ROOT / "config.yaml", encoding="utf-8"))
    cfg["analysis"]["provider"] = provider
    (TMP / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")


set_provider("heuristic")


@pytest.fixture(scope="session")
def sample_video():
    """3 minutes, 3 different 'scenes' (cuts at 60s and 120s), loud bursts every 37s."""
    out = TMP / "ep.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=60",
        "-f", "lavfi", "-i", "smptebars=s=640x360:r=25:d=60",
        "-f", "lavfi", "-i", "testsrc=s=640x360:r=25:d=60",
        "-f", "lavfi", "-i", "aevalsrc='0.1*sin(2*PI*220*t)*(1+8*lt(mod(t,37),2))':s=16000:d=180",
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
        "-map", "[v]", "-map", "3:a", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(out)], check=True)
    return out


@pytest.fixture(scope="session")
def sample_srt():
    lines = []
    for i in range(60):
        s, e = 3 * i + 0.2, 3 * i + 2.8
        words = "यह हिंदी संवाद की पंक्ति है" + (" और यह बहुत मज़ेदार भी है" if 100 <= s <= 150 else "")
        ts = lambda t: f"00:{int(t // 60):02d}:{int(t % 60):02d},{int(round((t % 1) * 1000)):03d}"  # noqa: E731
        lines.append(f"{i + 1}\n{ts(s)} --> {ts(e)}\n{words} {i + 1}{'?' if i % 7 == 0 else ''}\n")
    p = TMP / "ep.srt"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


@pytest.fixture()
def client():
    set_provider("heuristic")
    return TestClient(main.app)


def upload(client, video, srt=None):
    files = {"file": (video.name, open(video, "rb"), "video/mp4")}
    if srt:
        files["script"] = (srt.name, open(srt, "rb"), "text/plain")
    r = client.post("/api/videos", files=files)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def run_job(client, video_id):
    jobs.process_video(video_id)
    return client.get(f"/api/videos/{video_id}").json()


def check_clips(clips, duration, n=5, at_least=None):
    if at_least:  # tiny 3-minute test video: big AI picks can leave no room for a 5th clip
        assert at_least <= len(clips) <= n
        n = len(clips)
    assert len(clips) == n
    assert [c["rank"] for c in clips] == list(range(1, n + 1))
    for c in clips:
        assert 15 <= c["end"] - c["start"] <= 60, c
        assert c["pad_start"] == round(max(0, c["start"] - 5), 2)
        assert c["pad_end"] == round(min(duration, c["end"] + 5), 2)
        assert 0 <= c["start"] < c["end"] <= duration
    for i, a in enumerate(clips):
        for b in clips[i + 1:]:
            assert a["end"] <= b["start"] or b["end"] <= a["start"], "clips overlap"


def test_full_flow_with_srt(client, sample_video, sample_srt):
    vid = upload(client, sample_video, sample_srt)
    d = run_job(client, vid)
    assert d["status"] == "done", d["error"]
    check_clips(d["clips"], d["duration"])
    assert all(c["caption_gate"] == "ok" for c in d["clips"])  # script-verified captions
    vdir = settings.video_dir(vid)

    shots = __import__("json").loads((vdir / "shots.json").read_text())
    assert any(abs(t - 60) < 1 for t in shots) and any(abs(t - 120) < 1 for t in shots), shots
    events = __import__("json").loads((vdir / "audio_events.json").read_text())
    peak_times = [p["t"] for p in events["peaks"]]
    assert any(abs(t - 74) < 2 for t in peak_times), peak_times

    assert media.probe(vdir / "proxy.mp4")["height"] == 360  # never upscaled
    assert abs(len(list((vdir / "frames").glob("*.jpg"))) - 180) <= 1
    assert client.get(f"/api/videos/{vid}/frames/1").headers["content-type"] == "image/jpeg"
    tr = client.get(f"/api/videos/{vid}/transcript").json()
    assert tr["source"] == "srt" and len(tr["segments"]) == 60
    r = client.get(f"/api/videos/{vid}/proxy", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100  # browser seeking works


def test_ai_output_is_validated(client, sample_video, sample_srt, monkeypatch):
    set_provider("claude")
    bad = [
        {"start": 10, "end": 45, "score": 9, "title": "ठीक", "reason": "good"},
        {"start": 12, "end": 40, "score": 8, "title": "overlaps the first"},
        {"start": 100, "end": 105, "score": 7, "title": "too short"},
        {"start": 170, "end": 400, "score": 6, "title": "runs past the end"},
        {"start": 60, "end": 200, "score": 5, "title": "way too long"},
        {"title": "no times at all"},
        {"start": "abc", "end": "def"},
        "not even a dict",
    ]
    monkeypatch.setattr(llm, "ask_json", lambda *a, **k: bad)
    vid = upload(client, sample_video, sample_srt)
    d = run_job(client, vid)
    assert d["status"] == "done", d["error"]
    check_clips(d["clips"], d["duration"], at_least=4)
    sources = [c["source"] for c in d["clips"]]
    assert sources.count("claude") == 2 and "heuristic" in sources  # 2 valid AI clips, rest filled
    assert d["clips"][0]["title"] == "ठीक"
    assert "filled" in d["meta"]["pick"]["warning"]


def test_ai_failure_falls_back(client, sample_video, sample_srt, monkeypatch):
    set_provider("gemini")

    def boom(*a, **k):
        raise RuntimeError("no API key")

    monkeypatch.setattr(llm, "ask_json", boom)
    vid = upload(client, sample_video, sample_srt)
    d = run_job(client, vid)
    assert d["status"] == "done"
    check_clips(d["clips"], d["duration"])
    assert d["meta"]["pick"]["provider_used"] == "heuristic" and "failed" in d["meta"]["pick"]["warning"]


def test_rechoose_uses_cache(client, sample_video, sample_srt):
    vid = upload(client, sample_video, sample_srt)
    run_job(client, vid)
    mtime = (settings.video_dir(vid) / "proxy.mp4").stat().st_mtime
    assert client.post(f"/api/videos/{vid}/rechoose").status_code == 200
    d = run_job(client, vid)
    assert d["status"] == "done" and len(d["clips"]) == 5
    assert (settings.video_dir(vid) / "proxy.mp4").stat().st_mtime == mtime  # not rebuilt


def test_no_script_and_no_whisper_fails_clearly(client, sample_video):
    vid = upload(client, sample_video)
    d = run_job(client, vid)
    assert d["status"] == "failed" and d["error"]  # shown in the UI, worker keeps running


def test_input_checks(client, sample_video):
    assert client.get("/api/videos/not-an-id").status_code == 404
    assert client.get("/api/videos/" + "0" * 32).status_code == 404
    r = client.post("/api/videos", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400
    r = client.post("/api/videos", files={"file": ("a.mp4", b"x", "video/mp4"),
                                          "script": ("s.srt", b"garbage", "text/plain")})
    assert r.status_code == 400


def test_password(client, monkeypatch):
    monkeypatch.setenv("CLIPCUT_PASSWORD", "secret")
    assert client.get("/").status_code == 401
    assert client.get("/", auth=("anyone", "wrong")).status_code == 401
    assert client.get("/", auth=("anyone", "secret")).status_code == 200
