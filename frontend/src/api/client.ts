import type { AppStatus, Video, YouTubeStatus } from "./types";

async function errorMessage(r: Response): Promise<string> {
  try {
    const j = await r.json();
    if (typeof j.detail === "string") return j.detail;
  } catch { /* not JSON */ }
  return `Request failed (${r.status})`;
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(await errorMessage(r));
  return r.json();
}

export const api = {
  videos: () => getJson<Video[]>("/api/videos"),
  status: () => getJson<AppStatus>("/api/status"),
  youtube: () => getJson<YouTubeStatus>("/api/youtube/status"),
  async rechoose(id: string) {
    const r = await fetch(`/api/videos/${id}/rechoose`, { method: "POST" });
    if (!r.ok) throw new Error(await errorMessage(r));
  },
  frameUrl: (id: string, n: number) => `/api/videos/${id}/frames/${n}`,
  proxyUrl: (id: string) => `/api/videos/${id}/proxy`,
};

/** Upload with real progress (fetch can't report upload progress). */
export function uploadEpisode(
  video: File,
  script: File | null,
  onProgress: (fraction: number) => void,
): { promise: Promise<{ id: string }>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<{ id: string }>((resolve, reject) => {
    const fd = new FormData();
    fd.append("file", video);
    if (script) fd.append("script", script);
    xhr.open("POST", "/api/videos");
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
    xhr.onload = () => {
      let body: any = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300 && body?.id) resolve(body);
      else reject(new Error(typeof body?.detail === "string" ? body.detail : `Upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error("Network error — is the server running?"));
    xhr.onabort = () => reject(new Error("Upload cancelled"));
    xhr.send(fd);
  });
  return { promise, abort: () => xhr.abort() };
}
