import { useEffect, useState } from "react";
import { api } from "./api/client";
import type { Video } from "./api/types";
import { useTheme } from "./hooks/useTheme";
import { useVideos } from "./hooks/useVideos";
import { EpisodeCard } from "./components/EpisodeCard";
import { Pagination } from "./components/Pagination";
import { PlayerModal } from "./components/PlayerModal";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { UploadModal } from "./components/UploadModal";
import { Button } from "./components/ui";
import { Alert, Film, Upload } from "./components/icons";

const PAGE_SIZE = 5;

export default function App() {
  const { dark, toggle } = useTheme();
  const { videos, error, reload } = useVideos();
  const [aiKey, setAiKey] = useState<boolean | null>(null);
  const [youtube, setYoutube] = useState<boolean | null>(null);
  const [page, setPage] = useState(1);
  const [uploading, setUploading] = useState(false);
  const [playing, setPlaying] = useState<Video | null>(null);

  useEffect(() => {
    api.status().then((s) => setAiKey(s.ai_key)).catch(() => setAiKey(false));
    api.youtube().then((s) => setYoutube(!!s.connected)).catch(() => setYoutube(false));
  }, []);

  const total = videos?.length ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const current = Math.min(page, pages);
  const visible = (videos ?? []).slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  return (
    <div className="flex h-full">
      <Sidebar aiKey={aiKey} youtube={youtube} />
      <main className="min-w-0 flex-1 overflow-y-auto px-4 py-5 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-5xl">
          <TopBar dark={dark} onToggle={toggle} youtube={youtube} />

          <header className="mt-4 mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-4xl font-semibold tracking-tight">My <span className="text-[var(--accent)]">Episodes</span></h1>
              <p className="mt-1.5 text-[var(--muted)]">Manage your uploaded episodes and create viral clips.</p>
            </div>
            <Button variant="primary" onClick={() => setUploading(true)}><Upload className="text-lg" />Upload Episode</Button>
          </header>

          {error && (
            <div role="alert" className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-[var(--err)]/40 bg-[var(--err)]/10 p-3 text-sm text-[var(--err)]">
              <Alert className="text-base" /><span className="flex-1">Could not load episodes: {error}</span>
              <Button variant="outline" onClick={reload}>Retry</Button>
            </div>
          )}

          {videos === null && !error && (
            <div className="space-y-4" aria-busy="true" aria-label="Loading episodes">
              {[0, 1].map((i) => <div key={i} className="skeleton h-44 rounded-2xl border border-[var(--border)]" />)}
            </div>
          )}

          {videos !== null && total === 0 && (
            <div className="rounded-2xl border border-dashed border-[var(--border)] bg-[var(--surface)] px-6 py-16 text-center">
              <Film className="mx-auto text-5xl text-[var(--muted)]" />
              <h2 className="mt-4 text-lg font-semibold">No episodes yet</h2>
              <p className="mt-1 text-sm text-[var(--muted)]">Upload your first episode and ClipCUT will find the best moments.</p>
              <Button variant="primary" className="mt-5" onClick={() => setUploading(true)}><Upload />Upload Episode</Button>
            </div>
          )}

          <div className="space-y-4">
            {visible.map((v) => <EpisodeCard key={v.id} v={v} onPlay={setPlaying} onChanged={reload} />)}
          </div>
          <Pagination page={current} pages={pages} onChange={setPage} />
        </div>
      </main>

      {uploading && <UploadModal onClose={() => setUploading(false)} onUploaded={() => { setPage(1); reload(); }} />}
      {playing && <PlayerModal v={playing} onClose={() => setPlaying(null)} />}
    </div>
  );
}
