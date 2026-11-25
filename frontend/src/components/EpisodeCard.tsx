import { useState } from "react";
import { api } from "../api/client";
import type { Video } from "../api/types";
import { formatDuration, timeAgo, titleFromFilename } from "../lib/format";
import { Button, Chip } from "./ui";
import { Alert, Calendar, Check, Clock, External, Film, Pencil, Play, Refresh, Scissors, Upload } from "./icons";

function Thumb({ v }: { v: Video }) {
  const [failed, setFailed] = useState(false);
  // frames exist once the pipeline has captured them; n is 1-based (second n-1)
  const n = Math.max(1, Math.min(10, Math.floor(v.duration ?? 10)));
  const show = !failed && (v.status === "done" || v.progress >= 45);
  return (
    <div className="relative aspect-video w-full @3xl:w-64 shrink-0 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-2)]">
      {show ? (
        <img key={v.status} src={api.frameUrl(v.id, n)} alt="" loading="lazy" onError={() => setFailed(true)}
          className="h-full w-full object-cover" />
      ) : (
        <div className="grid h-full w-full place-items-center text-4xl text-[var(--muted)] opacity-50"><Film /></div>
      )}
    </div>
  );
}

function StatusRow({ ok, label, icon }: { ok: boolean; label: string; icon: React.ReactNode }) {
  return (
    <div className={`flex items-center gap-2 text-sm ${ok ? "text-[var(--ok)]" : "text-[var(--muted)]"}`}>
      <span className="text-lg">{ok ? <Check /> : icon}</span>{label}
    </div>
  );
}

export function EpisodeCard({ v, onPlay, onChanged }: { v: Video; onPlay: (v: Video) => void; onChanged: () => void }) {
  const [retrying, setRetrying] = useState(false);
  const [retryErr, setRetryErr] = useState<string | null>(null);
  const done = v.status === "done";
  const working = v.status === "queued" || v.status === "processing";
  const clips = v.clips ?? [];
  const approved = clips.filter((c) => c.approved).length;
  const posted = clips.find((c) => c.post_status === "done" && c.post_url);
  const height = v.meta?.video?.height;
  const dur = formatDuration(v.duration);

  const retry = async () => {
    setRetrying(true); setRetryErr(null);
    try { await api.rechoose(v.id); onChanged(); }
    catch (e) { setRetryErr(e instanceof Error ? e.message : "Retry failed"); }
    finally { setRetrying(false); }
  };

  return (
    <div className="@container"><article className="flex flex-col gap-5 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 @3xl:flex-row @3xl:items-center @3xl:p-5">
      <Thumb v={v} />

      <div className="min-w-0 space-y-3 @3xl:flex-1">
        <h2 className="truncate text-xl font-semibold tracking-tight" title={v.filename}>{titleFromFilename(v.filename)}</h2>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-[var(--muted)]">
          <span className="inline-flex items-center gap-1.5"><Calendar />Uploaded {timeAgo(v.created_at)}</span>
          {done && <span className="inline-flex items-center gap-1.5"><Scissors />{clips.length} {clips.length === 1 ? "Clip" : "Clips"} Ready</span>}
        </div>

        {working && (
          <div role="status" aria-live="polite">
            <div className="mb-1.5 flex justify-between text-xs text-[var(--muted)]">
              <span>{v.status === "queued" ? "Waiting in queue" : v.stage}</span><span>{Math.round(v.progress)}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[var(--surface-2)]">
              <div className="h-full rounded-full bg-[var(--accent)] transition-all duration-500" style={{ width: `${Math.max(2, v.progress)}%` }} />
            </div>
          </div>
        )}

        {v.status === "failed" && (
          <div className="flex items-start gap-2 rounded-lg border border-[var(--err)]/40 bg-[var(--err)]/10 p-3 text-sm text-[var(--err)]">
            <Alert className="mt-0.5 shrink-0 text-base" />
            <span className="break-words">{v.error || "Processing failed"}{retryErr && ` (${retryErr})`}</span>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {dur && <Chip icon={<Clock />}>{dur}</Chip>}
          {height ? <Chip icon={<Film />}>{height}p</Chip> : null}
        </div>
      </div>

      {done && (
        <div className="flex gap-6 @3xl:flex-col @3xl:gap-3 @3xl:border-l @3xl:border-[var(--border)] @3xl:pl-6 @3xl:w-44">
          <StatusRow ok={clips.length > 0 && approved === clips.length} icon={<Pencil />}
            label={clips.length && approved === clips.length ? "Edited" : approved ? `Edited ${approved}/${clips.length}` : "Not Edited"} />
          <StatusRow ok={!!posted} icon={<Upload />} label={posted ? "Posted" : "Not Posted"} />
        </div>
      )}

      <div className="flex flex-wrap gap-2 [&>*]:min-w-[6.5rem] @3xl:w-44 @3xl:shrink-0 @3xl:flex-col @3xl:flex-nowrap">
        <Button variant="primary" className="flex-1" disabled={!done} onClick={() => onPlay(v)}><Play />Play</Button>
        <Button className="flex-1" disabled title="Coming soon"><Pencil />Edit</Button>
        {posted ? (
          <a href={posted.post_url} target="_blank" rel="noreferrer"
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--text)] transition hover:border-[var(--accent)] hover:text-[var(--accent)]">
            <External />Open on YouTube
          </a>
        ) : v.status === "failed" ? (
          <Button className="flex-1" onClick={retry} disabled={retrying}><Refresh />{retrying ? "Retrying..." : "Retry"}</Button>
        ) : (
          <Button className="flex-1" disabled title="Coming soon"><Refresh />Render</Button>
        )}
      </div>
    </article></div>
  );
}
