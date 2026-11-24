# ClipCUT

Turns a finished Tenali Rama 3D episode into vertical shorts and promos with subtitles and
captions in every language, queues them for human review, then schedules and posts them.

## Setup (once, no admin or sudo needed)

**Windows (PowerShell)**
```powershell
winget install Python.Python.3.12        # skip if Python is already installed
winget install Gyan.FFmpeg               # then close and reopen PowerShell
cd ClipCUT
pip install -r requirements.txt
$env:ANTHROPIC_API_KEY = "sk-ant-..."    # your Claude API key (set again in each new window)
```

**Mac / Linux**
```bash
brew install ffmpeg                      # Linux: use your package manager, or a static ffmpeg build
cd ClipCUT && pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

**Fonts (needed for Hindi/Telugu subtitles):** download the .ttf files from fonts.google.com
(Noto Sans Devanagari, Noto Sans Telugu, Noto Sans) and drop them in the `fonts/` folder.
No installing needed.

Then open `config.yaml` and set `source_language` and `languages` to your launch languages.

## Daily use

(On Mac/Linux use `python3` instead of `python`.)

```
python pipeline.py process episode01.mp4 --episode-id ep01   # clips + subtitles + captions
```
Open `review.csv` in Google Sheets. Fill `decision` with approve or reject. Fix wording in
`edited_title` / `edited_caption`. Rows with needs_review=1 come first. Save as CSV, then:
```
python pipeline.py import-review review.csv                  # save decisions
python pipeline.py schedule                                  # assign posting slots
python pipeline.py run                                       # posts what is due (leave running)
```

Clips are saved in `work/<episode-id>/clipNN_<lang>/`.

## What works now (tested end to end)

- Clip picking with validation (length, overlap, scene-cut snapping)
- 9:16 vertical render with blurred background and burned-in subtitles
- Per-language subtitles + title + caption + hashtags, with a line-count safety check
- Review queue via CSV (works in Google Sheets and Excel, Telugu/Hindi safe)
- Scheduler with daily slots, retries (3x, 15 min apart) and a SQLite log

`python tests/smoke_test.py` runs the whole flow on a fake video with a fake AI (no key needed).

## What is NOT done yet

1. **Real transcription and AI quality are untested** on a real Tenali Rama episode. Run one
   episode and review the picks and translations before trusting them.
2. **Platform adapters** (`agent/publishers/stubs.py`) are placeholders. The scheduler runs in
   dry-run mode (`publishing.dry_run: true`) and only logs what it would post. Each adapter
   needs API access first:
   - Instagram/Facebook: Meta developer app + app review, Business account linked to a Page
   - YouTube: Google Cloud project + OAuth consent; request more quota if posting a lot
   - TikTok: Content Posting API app + audit (posts are private until approved)
   - X: developer account, pay-per-use billing
3. Developed and tested on Linux. Windows should work but has not been tried yet; tell me if
   anything fails.

---

# ClipCUT server (Milestone 1): upload -> analysis -> 5 proposed clips

A web app. The team opens a page, uploads an episode (and optionally its Hindi `.srt`), and gets
back the transcript, shot changes, loud moments and 5 proposed clips (each with 5 s of padding on
both sides) to review on a player. The editing screen (trim handles, draggable 9:16 crop window)
is the next milestone; this one produces everything that screen needs.

## Run it

```
pip install -r requirements.txt
python run_server.py                 # then open http://localhost:8000
```
(Windows PowerShell: set keys with `$env:NAME = "value"` before running.)

Optional environment variables:
- `CLIPCUT_PASSWORD`: require this password (any username) for the whole site. Set it, because the episodes are unreleased.
- `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`: only for `analysis.provider: claude` / `gemini` in `config.yaml`.
- `CLIPCUT_DATA`: where uploads and results are stored (default `./data`).

## Transcripts (the Hindi accuracy problem)

1. **Best: upload the `.srt` with the video.** It is used as-is, with full confidence, and captions are on by default.
2. Otherwise faster-whisper transcribes the audio (set `analysis.asr` in `config.yaml`; use `compute_type: int8` on CPU).
   Each clip gets a caption confidence; below `caption_conf_threshold` its captions default to OFF in the editor.
   That threshold is a guess: calibrate it on real episodes.

## AI providers (`analysis.provider` in config.yaml)

- `heuristic`: no AI. Picks busy, loud, punchy moments. For testing without keys, and used as automatic fallback.
- `claude`: Claude reads the dialogue + shots + loud moments and proposes clips. Code then validates every pick (length, overlaps, snapping to sentence/shot boundaries).
- `gemini`: same, via the Gemini API. Check Google AI Studio for the current model name. The free tier may use your data to improve Google products, so do not send unreleased episodes through it.

If the AI fails (no key, no network, bad output) the heuristic picker fills in, and the page shows a warning.

## Where results are stored

`data/videos/<id>/`: `original.*`, `proxy.mp4` (small, seek-friendly copy for the browser), `audio.wav`,
`frames/` (one thumbnail per second, `frame_00001.jpg` = second 0), `transcript.json`, `shots.json`, `audio_events.json`.
Slow steps are cached, so "Choose clips again" is fast.

## Tests

`pip install pytest httpx` then `pytest tests/test_server.py -q`. Uses real FFmpeg on a synthetic
video: shot detection, loudness peaks, proxy, thumbnails, Range requests, clip validation against
bad AI output, AI-failure fallback, caching, input checks, password.

## What is verified and what is not

Verified here: everything in the test list above, plus a live run of the server with its worker.
**Not verified yet:** Whisper on real Hindi audio (model downloads were blocked in my environment),
real Claude/Gemini calls, and the web page in a real browser. Try those first on one real episode.

## Not built yet

Editing screen (trim + draggable crop window + keyframes), crop auto-suggestions (character detector),
rendering from the editor's decisions, posting adapters, vocal separation (Demucs), aligning an
untimed script to the audio, LLM clean-up of ASR text, vision analysis of frames.

## Testing Hindi transcript quality on your own video

1. `pip install -r requirements.txt`, then `python run_server.py` and open http://localhost:8000.
2. Upload the raw video (no .srt, so Whisper runs). The first run downloads the speech model.
3. When it finishes, open "Transcript" under the player. Click lines to jump to that moment and
   judge the Hindi by ear. Red lines are the ones the model itself is unsure about.
4. Speed vs quality: `analysis.asr.model` in `config.yaml`. `small` is fast on any laptop;
   `large-v3` is the best Whisper option but wants an NVIDIA GPU (set `compute_type: float16`).
   Delete `data/videos/<id>/transcript.json` and press "Choose clips again" to re-run with another model.
