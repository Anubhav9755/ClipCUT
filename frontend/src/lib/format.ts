export function timeAgo(epochSeconds: number, now = Date.now()): string {
  const s = Math.max(0, Math.floor(now / 1000 - epochSeconds));
  if (s < 60) return "just now";
  const units: [number, string][] = [[86400, "day"], [3600, "hour"], [60, "minute"]];
  for (const [size, name] of units) {
    if (s >= size) { const n = Math.floor(s / size); return `${n} ${name}${n === 1 ? "" : "s"} ago`; }
  }
  return "just now";
}

export function formatDuration(sec: number | null | undefined): string | null {
  if (sec == null || !isFinite(sec)) return null;
  const t = Math.round(sec), h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60;
  const p = (n: number) => String(n).padStart(2, "0");
  return h ? `${h}:${p(m)}:${p(s)}` : `${m}:${p(s)}`;
}

export function titleFromFilename(name: string): string {
  return (name || "Untitled").replace(/\.[^.]+$/, "").replace(/[_]+/g, " ").trim() || "Untitled";
}

export const MAX_UPLOAD_BYTES = 2 * 1024 ** 3;
export const VIDEO_EXTS = [".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"];
export const extOf = (n: string) => (n.match(/\.[^.]+$/)?.[0] ?? "").toLowerCase();
export function formatBytes(b: number): string {
  return b >= 1024 ** 3 ? `${(b / 1024 ** 3).toFixed(1)} GB` : `${Math.max(1, Math.round(b / 1024 ** 2))} MB`;
}
