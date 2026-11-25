import { useEffect, useRef, useState } from "react";
import { uploadEpisode } from "../api/client";
import { MAX_UPLOAD_BYTES, VIDEO_EXTS, extOf, formatBytes } from "../lib/format";
import { Button } from "./ui";
import { Alert, Close, Doc, Film, Upload } from "./icons";

export function validateVideo(f: File): string | null {
  if (!VIDEO_EXTS.includes(extOf(f.name))) return `Unsupported file type. Use one of: ${VIDEO_EXTS.join(", ")}`;
  if (f.size > MAX_UPLOAD_BYTES) return "That file is over the 2 GB limit.";
  if (f.size === 0) return "That file is empty.";
  return null;
}

export function UploadModal({ onClose, onUploaded }: { onClose: () => void; onUploaded: () => void }) {
  const [video, setVideo] = useState<File | null>(null);
  const [script, setScript] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const abortRef = useRef<(() => void) | null>(null);
  const videoInput = useRef<HTMLInputElement>(null);
  const srtInput = useRef<HTMLInputElement>(null);

  const close = () => { abortRef.current?.(); onClose(); };
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  const pick = (f: File | undefined | null) => {
    if (!f) return;
    const err = validateVideo(f);
    setError(err); setVideo(err ? null : f);
  };
  const pickScript = (f: File | undefined | null) => {
    if (!f) return;
    if (extOf(f.name) !== ".srt") { setError("The optional script must be an .srt file."); return; }
    setError(null); setScript(f);
  };

  const start = async () => {
    if (!video) return;
    setBusy(true); setError(null); setProgress(0);
    const up = uploadEpisode(video, script, setProgress);
    abortRef.current = up.abort;
    try {
      await up.promise;
      abortRef.current = null;
      onUploaded(); onClose();
    } catch (e) {
      abortRef.current = null;
      setError(e instanceof Error ? e.message : "Upload failed");
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4" onMouseDown={() => !busy && close()} role="dialog" aria-modal="true" aria-label="Upload episode">
      <div className="w-full max-w-xl rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6" onMouseDown={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">Upload Episode</h3>
          <button onClick={close} aria-label="Close" className="text-xl text-[var(--muted)] hover:text-[var(--text)]"><Close /></button>
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); if (!busy) setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); if (!busy) pick(e.dataTransfer.files[0]); }}
          className={`rounded-xl border-2 border-dashed p-8 text-center transition ${drag ? "border-[var(--accent)] bg-[var(--surface-2)]" : "border-[var(--border)]"}`}>
          <Upload className="mx-auto text-5xl text-[var(--accent)]" />
          {video ? (
            <div className="mt-3 flex items-center justify-center gap-2 text-sm">
              <Film className="text-[var(--muted)]" /><span className="truncate max-w-[18rem]">{video.name}</span>
              <span className="text-[var(--muted)]">({formatBytes(video.size)})</span>
            </div>
          ) : (
            <>
              <p className="mt-3 font-medium">Drag and drop your video here</p>
              <p className="text-sm text-[var(--muted)]">or click to browse</p>
            </>
          )}
          <input ref={videoInput} type="file" hidden accept={VIDEO_EXTS.join(",")} onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
          <Button variant={video ? "outline" : "primary"} className="mt-4" disabled={busy} onClick={() => videoInput.current?.click()}>
            {video ? "Choose a different file" : "Browse Files"}
          </Button>
          <p className="mt-3 text-xs text-[var(--muted)]">Supports MP4, MOV, MKV, AVI, WebM, M4V · Up to 2 GB</p>
        </div>

        <div className="mt-4 flex items-center gap-3 text-sm">
          <Doc className="text-lg text-[var(--muted)]" />
          <span className="text-[var(--muted)]">Optional SRT file:</span>
          {script ? (
            <span className="inline-flex items-center gap-2 truncate">
              <span className="truncate max-w-[10rem]">{script.name}</span>
              <button disabled={busy} onClick={() => setScript(null)} aria-label="Remove SRT" className="text-[var(--muted)] hover:text-[var(--text)]"><Close /></button>
            </span>
          ) : (
            <button disabled={busy} onClick={() => srtInput.current?.click()} className="text-[var(--accent)] hover:underline disabled:opacity-40">Add .srt</button>
          )}
          <input ref={srtInput} type="file" hidden accept=".srt" onChange={(e) => { pickScript(e.target.files?.[0]); e.target.value = ""; }} />
        </div>

        {busy && (
          <div className="mt-4" role="status" aria-live="polite">
            <div className="mb-1.5 flex justify-between text-xs text-[var(--muted)]">
              <span>{progress >= 1 ? "Finishing up..." : "Uploading..."}</span><span>{Math.round(progress * 100)}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[var(--surface-2)]">
              <div className="h-full rounded-full bg-[var(--accent)] transition-all" style={{ width: `${progress * 100}%` }} />
            </div>
          </div>
        )}

        {error && (
          <div role="alert" className="mt-4 flex items-start gap-2 rounded-lg border border-[var(--err)]/40 bg-[var(--err)]/10 p-3 text-sm text-[var(--err)]">
            <Alert className="mt-0.5 shrink-0 text-base" /><span>{error}</span>
          </div>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={close}>{busy ? "Cancel upload" : "Cancel"}</Button>
          <Button variant="primary" disabled={!video || busy} onClick={start}><Upload />Upload</Button>
        </div>
      </div>
    </div>
  );
}
