import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Video } from "../api/types";

const POLL_MS = 2000;

/** Loads episodes; keeps polling every 2s only while something is queued/processing. */
export function useVideos() {
  const [videos, setVideos] = useState<Video[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const alive = useRef(true);

  const load = useCallback(async () => {
    window.clearTimeout(timer.current);
    let busy = true; // on error keep retrying
    try {
      const v = await api.videos();
      if (!alive.current) return;
      setVideos(v);
      setError(null);
      busy = v.some((x) => x.status === "queued" || x.status === "processing");
    } catch (e) {
      if (!alive.current) return;
      setError(e instanceof Error ? e.message : "Could not load episodes");
    }
    if (alive.current && busy) timer.current = window.setTimeout(load, POLL_MS);
  }, []);

  useEffect(() => {
    alive.current = true;
    load();
    return () => { alive.current = false; window.clearTimeout(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { videos, error, reload: load };
}
