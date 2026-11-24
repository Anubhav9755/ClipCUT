#!/usr/bin/env python3
"""ClipCUT.

  python pipeline.py process episode.mp4 --episode-id ep01   # transcribe, pick, cut, translate
  python pipeline.py export-review                           # -> review.csv (open in Google Sheets)
  python pipeline.py import-review review.csv                # reviewer decisions back in
  python pipeline.py schedule                                # queue approved clips into daily slots
  python pipeline.py run                                     # post whatever is due (keeps running)
"""
import argparse
import json
from pathlib import Path

from agent import config as cfgmod, cut, db, pick_clips, review, scheduler, transcribe, translate


def font_for(cfg, lang):
    fonts = cfg["subtitles"]["fonts"]
    return fonts.get(lang, fonts["default"])


def process(cfg, conn, video: Path, episode_id: str, force: bool):
    if db.episode_has_clips(conn, episode_id):
        if not force:
            raise SystemExit(f"Episode '{episode_id}' already processed. Use --force to redo it.")
        db.clear_episode(conn, episode_id)

    work = Path(cfg["paths"]["work_dir"]) / episode_id
    work.mkdir(parents=True, exist_ok=True)

    # 1. transcribe (cached, so re-runs are free)
    tpath = work / "transcript.json"
    if tpath.exists():
        print("Using saved transcript")
        transcript = json.loads(tpath.read_text(encoding="utf-8"))
    else:
        print("Transcribing...")
        transcript = transcribe.run(video, cfg)
        tpath.write_text(json.dumps(transcript, ensure_ascii=False, indent=1), encoding="utf-8")

    # 2. pick clips
    print("Picking clips...")
    duration = pick_clips.probe_duration(video)
    scene_cuts = pick_clips.detect_scenes(video)
    clips = pick_clips.pick(transcript["segments"], scene_cuts, cfg, duration)
    print(f"  {len(clips)} clips chosen")

    # 3-4. per clip, per language: translate + render
    for n, clip in enumerate(clips, 1):
        clip_id = db.add_clip(conn, episode_id, clip)
        cues = translate.cues_for_clip(transcript["cues"], clip["start"], clip["end"])
        if not cues:
            print(f"  clip {n}: no dialogue found, skipping")
            continue
        for lang in cfg["languages"]:
            print(f"  clip {n}/{len(clips)} [{lang}] {clip['title']}")
            v = translate.make_variant(cues, clip, lang, cfg)
            out_dir = work / f"clip{n:02d}_{lang}"
            out_dir.mkdir(exist_ok=True)
            srt = out_dir / "subs.srt"
            srt.write_text(translate.to_srt(cues, v["subtitles"]), encoding="utf-8")
            mp4 = out_dir / f"{episode_id}_clip{n:02d}_{lang}.mp4"
            cut.render(video, clip["start"], clip["end"], srt, mp4, font_for(cfg, lang))
            db.add_variant(conn, clip_id, lang, mp4, srt, v)

    count = review.export_csv(conn, cfg["paths"]["review_csv"])
    print(f"\nDone. {count} items waiting for review in {cfg['paths']['review_csv']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("process", help="turn an episode into clips")
    p.add_argument("video")
    p.add_argument("--episode-id", required=True)
    p.add_argument("--force", action="store_true", help="redo an episode that was already processed")

    sub.add_parser("export-review", help="write review.csv")
    r = sub.add_parser("import-review", help="read reviewer decisions")
    r.add_argument("csv")
    sub.add_parser("schedule", help="queue approved clips into posting slots")
    s = sub.add_parser("run", help="post due items")
    s.add_argument("--once", action="store_true", help="check once and exit")

    args = ap.parse_args()
    cfg = cfgmod.load()
    conn = db.connect(cfg["paths"]["db"])

    if args.cmd == "process":
        process(cfg, conn, Path(args.video), args.episode_id, args.force)
    elif args.cmd == "export-review":
        print(f"{review.export_csv(conn, cfg['paths']['review_csv'])} rows -> {cfg['paths']['review_csv']}")
    elif args.cmd == "import-review":
        print(review.import_csv(conn, args.csv))
    elif args.cmd == "schedule":
        print(f"{scheduler.schedule_approved(conn, cfg)} posts queued")
    elif args.cmd == "run":
        if args.once:
            print(f"Posted {scheduler.run_due(conn, cfg)}")
        else:
            scheduler.loop(conn, cfg)


if __name__ == "__main__":
    main()
