"""Step 4: FFmpeg cuts the clip, makes it 9:16 vertical and burns in subtitles."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FRAME_H = 1920
FONT_PX = 60          # subtitle text size
OUTLINE_PX = 5
BOTTOM_MARGIN_PX = 300  # keeps text clear of the app buttons at the bottom of Reels/Shorts
SIDE_MARGIN_PX = 90


def render(video: Path, start: float, end: float, srt: Path, out: Path, font: str) -> None:
    duration = end - start
    # libass scales SRT styles against a 288-unit-high canvas, so we convert pixel sizes
    # (for our 1920px-high frame) into that scale. Edit the pixel values above to restyle.
    k = 288 / FRAME_H
    style = (
        f"FontName={font},FontSize={FONT_PX * k:.1f},Bold=1,PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,BorderStyle=1,Outline={OUTLINE_PX * k:.2f},Shadow=0,Alignment=2,"
        f"MarginV={BOTTOM_MARGIN_PX * k:.1f},MarginL={SIDE_MARGIN_PX * k:.1f},MarginR={SIDE_MARGIN_PX * k:.1f}"
    )
    # Fonts dropped into the project's fonts/ folder are used directly (no system install needed).
    fontsdir = ""
    fonts = ROOT / "fonts"
    if fonts.is_dir() and any(fonts.glob("*.[to]tf")):
        try:
            fontsdir = ":fontsdir=" + os.path.relpath(fonts, srt.parent).replace("\\", "/")
        except ValueError:  # different drive on Windows: fall back to system fonts
            pass
    # Blurred, zoomed copy fills the 9:16 frame; the sharp original sits on top in the middle.
    graph = (
        "[0:v]split=2[bg][fg];"
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[b];"
        "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[f];"
        "[b][f]overlay=(W-w)/2:(H-h)/2,"
        f"subtitles={srt.name}{fontsdir}:force_style='{style}'[v]"
    )
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start:.2f}", "-i", str(video.resolve()), "-t", f"{duration:.2f}",
        "-filter_complex", graph, "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        str(out.resolve()),
    ]
    # run inside the SRT's folder so the filter can use a plain filename (no path escaping issues)
    subprocess.run(cmd, check=True, cwd=srt.parent)
