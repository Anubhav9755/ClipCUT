"""The analysis job: upload -> proxy, audio, thumbnails, shots, transcript, loudness -> 5 proposed clips."""
import json
import logging
import threading
import time

from . import audio_events, db, media, picker, settings, transcript

log = logging.getLogger("clipcut")


def _cached(path, build):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    data = build()
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def process_video(video_id: str) -> None:
    cfg = settings.cfg()
    a = cfg["analysis"]
    vdir = settings.video_dir(video_id)
    try:
        src = next(vdir.glob("original.*"))
        db.set_stage(video_id, "Reading the video", 5)
        info = media.probe(src)
        db.set_duration(video_id, info["duration"])
        db.set_stage(video_id, "Reading the video", 8, video=info)

        proxy = vdir / "proxy.mp4"
        if not proxy.exists():
            db.set_stage(video_id, "Making the editing preview", 12)
            media.make_proxy(src, proxy, a["proxy_height"], info["fps"])

        audio = vdir / "audio.wav"
        if info["has_audio"] and not audio.exists():
            db.set_stage(video_id, "Extracting audio", 30)
            media.extract_audio(src, audio)

        frames = vdir / "frames"
        if not frames.exists():
            db.set_stage(video_id, "Capturing frames", 40)
            media.extract_frames(proxy, frames)

        db.set_stage(video_id, "Finding shot changes", 50)
        shots = _cached(vdir / "shots.json", lambda: media.detect_shots(proxy, a["scene_threshold"]))

        def build_transcript():
            script = vdir / "script.srt"
            if script.exists():
                return transcript.from_srt(script)
            if info["has_audio"]:
                db.set_stage(video_id, "Transcribing the dialogue", 55)
                return transcript.from_whisper(audio, a["asr"])
            return {"source": "none", "language": None, "segments": []}

        tr = _cached(vdir / "transcript.json", build_transcript)

        db.set_stage(video_id, "Finding loud and exciting moments", 85)
        ev = (_cached(vdir / "audio_events.json", lambda: audio_events.analyze(audio))
              if info["has_audio"] else {"window": 0.5, "z": [], "peaks": []})

        db.set_stage(video_id, "Choosing the best clips", 90)
        clips, pick_info = picker.pick(tr, shots, ev, info["duration"], cfg)
        db.replace_clips(video_id, clips)
        db.set_stage(video_id, "Choosing the best clips", 99, pick=pick_info, shots=len(shots),
                     transcript_source=tr["source"], segments=len(tr["segments"]))
        db.set_done(video_id)
    except Exception as e:  # keep the worker alive; show the reason in the UI
        log.exception("Job failed for %s", video_id)
        db.set_failed(video_id, str(e))


def worker_loop(stop: threading.Event) -> None:
    while not stop.is_set():
        vid = db.claim_next()
        if vid:
            process_video(vid)
        else:
            time.sleep(2)
