# ClipCUT

**AI-powered animated video to vertical shorts editor.**

ClipCUT transforms full-length animated episodes into engaging, ready-to-publish vertical videos. It automatically identifies interesting moments, generates clip suggestions, detects scene changes, and provides an interactive editor for trimming and framing scenes into a 9:16 format.

The goal is simple: let AI handle the repetitive work while keeping the final creative decisions in human hands.

---

## Features

- **AI-Powered Clip Selection** — Automatically analyzes episodes and selects the five most engaging moments based on dialogue, context, and scene information.
- **Automatic Scene Detection** — Detects scene transitions and creates keyframes for easier editing.
- **Interactive Video Editor** — Review clips scene by scene with a draggable crop window and real-time vertical preview.
- **Smart Crop Keyframes** — Position the crop window for different scenes with cut and smooth pan transitions.
- **Clip Trimming** — Adjust start and end times with a visual timeline.
- **Hindi Captions** — Automatically generates captions from transcripts with support for Devanagari fonts.
- **High-Quality Rendering** — Exports optimized vertical videos in 1080 × 1920 resolution.
- **AI-Generated YouTube Metadata** — Generates titles, descriptions, and tags using Claude.
- **YouTube Integration** — Connect your account, review metadata, choose visibility, and upload directly.
- **Background Processing** — Video analysis, rendering, and uploads run in background workers.
- **Local Storage** — Episodes, edits, renders, and processing data are stored locally.

---

## Workflow

1. Upload a full-length episode.
2. ClipCUT analyzes the video and dialogue.
3. AI selects five potential clips.
4. Review the selected clips and their timestamps.
5. Open a clip in the editor.
6. Adjust the crop window scene by scene.
7. Trim the clip and review captions.
8. Approve the edit.
9. Render the final vertical video.
10. Generate YouTube metadata and publish.

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Frontend | HTML, CSS, JavaScript |
| Database | SQLite |
| Video Processing | FFmpeg, FFprobe |
| AI | Anthropic Claude API |
| Transcription | Speech-to-text pipeline |
| Captions | FFmpeg subtitles, libass |
| Fonts | Noto Sans, Noto Sans Devanagari, Noto Sans Telugu |
| YouTube Integration | YouTube Data API v3 |
| Authentication | Google OAuth 2.0 |

---

## Architecture

```text
                    ┌──────────────────────┐
                    │      Browser         │
                    │   ClipCUT Editor     │
                    └──────────┬───────────┘
                               │
                          HTTP / JSON
                               │
                    ┌──────────▼───────────┐
                    │    FastAPI Server   │
                    │     main.py         │
                    └──────────┬───────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
   Video Analysis          Editor API          Render Worker
          │                    │                    │
          ▼                    ▼                    ▼
   Transcription         Saved Keyframes       FFmpeg
   Scene Detection       Trim & Crop            Captions
   AI Clip Selection    Edit Decisions         Final Video
          │                                         │
          └────────────────────┬────────────────────┘
                               │
                    ┌──────────▼───────────┐
                    │   SQLite Database   │
                    │   Local Storage     │
                    └─────────────────────┘
                               │
                    ┌──────────▼───────────┐
                    │   YouTube Upload    │
                    │  Google OAuth + API │
                    └─────────────────────┘
```

---

## Project Structure

```text
ClipCUT/
│
├── run_server.py
├── pipeline.py
├── requirements.txt
├── config.yaml
├── .env
├── .gitignore
│
├── server/
│   ├── main.py
│   ├── db.py
│   ├── jobs.py
│   ├── media.py
│   ├── transcript.py
│   ├── picker.py
│   ├── llm.py
│   ├── audio_events.py
│   ├── render.py
│   ├── captions.py
│   ├── youtube.py
│   ├── settings.py
│   └── static/
│       └── index.html
│
├── fonts/
│   ├── Noto_Sans/
│   ├── Noto_Sans_Devanagari/
│   └── Noto_Sans_Telugu/
│
├── tests/
│   ├── smoke_test.py
│   └── test_server.py
│
├── data/
│   ├── clipcut.db
│   └── videos/
│       └── <video_id>/
│           ├── original video
│           ├── proxy.mp4
│           ├── transcript.json
│           ├── thumbnails/
│           └── renders/
│
└── agent/
    └── Previous scheduling components
```

---

## Installation

### Prerequisites

- Python 3.10+
- FFmpeg and FFprobe
- Anthropic API key
- Google Cloud project (required for YouTube uploads)

Verify FFmpeg installation:

```bash
ffmpeg -version
ffprobe -version
```

Make sure FFmpeg includes subtitle support through `libass`.

### 1. Clone the repository

```bash
git clone https://github.com/Anubhav9755/ClipCUT.git
cd ClipCUT
```

### 2. Create a virtual environment

**Windows:**

```powershell
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

For YouTube integration, install:

```bash
pip install google-api-python-client google-auth-oauthlib
```

Optional:

```bash
pip install fonttools
```

### 4. Configure environment variables

Create a `.env` file in the root directory:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
CLIPCUT_PASSWORD=your_secure_password
CLIPCUT_MODEL=your_preferred_model
```

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | API key for AI-powered clip selection and metadata generation |
| `CLIPCUT_PASSWORD` | Optional password to protect access to the application |
| `CLIPCUT_MODEL` | Optional model override for metadata generation |

**Never commit your `.env` file or API credentials to GitHub.**

### 5. Start the application

```bash
python run_server.py
```

Open your browser:

**http://localhost:8000**

---

## Video Editing

### Scene-by-scene editing

ClipCUT automatically detects scene changes and creates crop keyframes.

The editor allows you to:

- Navigate between scenes.
- Move the vertical crop window.
- Add or remove keyframes.
- Choose cut or pan transitions.
- Trim the clip.
- Preview captions.
- Approve completed edits.

### Keyframe transitions

| Mode | Description |
|---|---|
| Cut | Instantly changes crop position |
| Pan | Smoothly moves the crop window between keyframes |

### Output format

| Property | Value |
|---|---|
| Resolution | 1080 × 1920 |
| Aspect Ratio | 9:16 |
| Video Codec | H.264 |
| Audio Codec | AAC |
| Audio Bitrate | 192 kbps |
| Video Quality | CRF 18 |
| Frame Rate | Matches source frame rate |
| Audio Normalization | Approximately −16 LUFS |

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Space` | Play / Pause |
| `←` / `→` | Move one frame |
| `Shift + ←` / `Shift + →` | Move one second |
| `N` | Next scene |
| `P` | Previous scene |
| `C` | Add a scene cut |
| `K` | Add a keyframe |
| `Delete` | Remove selected keyframe |
| `Esc` | Close editor |

---

## YouTube Integration

ClipCUT supports direct YouTube uploads using the YouTube Data API v3.

### Setup

1. Create a project in Google Cloud Console.
2. Enable the YouTube Data API v3.
3. Configure the OAuth consent screen.
4. Create OAuth credentials for a Desktop application.
5. Store the downloaded OAuth configuration locally as `client_secret.json`.
6. Start ClipCUT and connect your YouTube account.

OAuth tokens are stored locally and should never be committed to the repository.

### Publishing workflow

1. Render a clip.
2. Click **Post to YouTube**.
3. Generate a title, description, and tags using AI.
4. Review and edit the metadata.
5. Select visibility: Private, Unlisted, or Public.
6. Approve and upload.

---

## API Routes

| Endpoint | Description |
|---|---|
| `POST /api/videos` | Upload an episode |
| `GET /api/videos` | List uploaded episodes |
| `GET /api/videos/{id}` | Retrieve episode details and clips |
| `POST /api/videos/{id}/rechoose` | Re-select clips |
| `GET /api/videos/{id}/proxy` | Stream the preview video |
| `GET /api/videos/{id}/transcript` | Retrieve transcript |
| `GET /api/clips/{id}/edit` | Retrieve clip edit |
| `PUT /api/clips/{id}/edit` | Save clip edit |
| `GET /api/clips/{id}/shots` | Detect scene changes |
| `GET /api/clips/{id}/captions` | Retrieve caption cues |
| `POST /api/clips/{id}/render` | Render clip |
| `GET /api/clips/{id}/render` | Check rendering status |
| `GET /api/clips/{id}/render/file` | Play or download rendered video |
| `GET /api/youtube/status` | Check YouTube connection |
| `GET /api/youtube/connect` | Connect YouTube account |
| `POST /api/clips/{id}/youtube/metadata` | Generate YouTube metadata |
| `POST /api/clips/{id}/youtube/upload` | Upload clip |
| `GET /api/status` | Check application status |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| AI API key not detected | Check `.env` and restart the server |
| AI clip selection fails | Verify API key and model configuration |
| Scene detection fails | Restart server and check FFmpeg installation |
| Rendering fails | Verify FFmpeg and subtitle support |
| FFmpeg not found | Add FFmpeg to system PATH |
| Captions missing | Check fonts and transcript availability |
| YouTube not connected | Complete Google OAuth setup |
| YouTube uploads remain private | New or unverified Google projects may have upload restrictions |
| Preview audio synchronization issues | Check proxy generation and source frame rate |

---

## Security

- API keys are stored in environment variables.
- OAuth credentials and tokens are stored locally.
- Generated videos and uploaded episodes remain local.
- Set `CLIPCUT_PASSWORD` before exposing the application to a shared network.
- Do not commit secrets, OAuth tokens, or private media files.

---

## Current Limitations

- Automatic crop positioning is not yet fully AI-driven.
- Preview audio synchronization may vary with source videos.
- Cropping lower-resolution footage may result in softness.
- Caption accuracy depends on transcript quality.
- YouTube OAuth and real upload workflows may require additional testing.
- The application is primarily designed for local, single-user operation.

---

## Roadmap

- AI-assisted character detection and automatic crop positioning.
- Improved subject tracking across scenes.
- Better preview audio synchronization.
- Automatic caption alignment using verified scripts.
- Visual scene understanding for improved clip selection.
- Instagram and Facebook publishing.
- TikTok publishing integration.
- Scheduled uploads.
- Analytics and engagement tracking.
- Cost tracking and error monitoring.
- Multi-user support and shared storage.

---

## License

License not yet specified.

---

## Author

**Anubhav**

GitHub: [@Anubhav9755](https://github.com/Anubhav9755)

Repository: [ClipCUT](https://github.com/Anubhav9755/ClipCUT)
