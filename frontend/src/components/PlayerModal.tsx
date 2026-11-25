import { useEffect } from "react";
import { api } from "../api/client";
import type { Video } from "../api/types";
import { titleFromFilename } from "../lib/format";
import { Close } from "./icons";

export function PlayerModal({ v, onClose }: { v: Video; onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4" onMouseDown={onClose} role="dialog" aria-modal="true" aria-label="Video preview">
      <div className="w-full max-w-4xl rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4" onMouseDown={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="truncate font-semibold">{titleFromFilename(v.filename)}</h3>
          <button onClick={onClose} aria-label="Close" className="text-xl text-[var(--muted)] hover:text-[var(--text)]"><Close /></button>
        </div>
        <video src={api.proxyUrl(v.id)} controls autoPlay className="aspect-video w-full rounded-lg bg-black" />
      </div>
    </div>
  );
}
