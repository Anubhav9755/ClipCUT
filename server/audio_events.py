"""Loudness analysis: finds laughter/shouts/music hits as moments where volume jumps."""
import wave

import numpy as np

WINDOW = 0.5  # seconds


def analyze(wav_path) -> dict:
    with wave.open(str(wav_path), "rb") as w:
        rate, n = w.getframerate(), w.getnframes()
        data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    step = int(rate * WINDOW)
    if len(data) < step:
        return {"window": WINDOW, "z": [], "peaks": []}
    usable = len(data) // step * step
    rms = np.sqrt((data[:usable].reshape(-1, step) ** 2).mean(axis=1))
    std = rms.std() or 1.0
    z = (rms - rms.mean()) / std
    peaks = []
    for i, val in enumerate(z):
        if val > 1.5 and val >= z[max(0, i - 2): i + 3].max():
            t = round(i * WINDOW, 2)
            if not peaks or t - peaks[-1]["t"] > 2.0:
                peaks.append({"t": t, "z": round(float(val), 2)})
    return {"window": WINDOW, "z": [round(float(v), 2) for v in z], "peaks": peaks}
