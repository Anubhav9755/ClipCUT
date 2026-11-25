import { Moon, Sun } from "./icons";

export function TopBar({ dark, onToggle, youtube }: { dark: boolean; onToggle: () => void; youtube: boolean | null }) {
  return (
    <div className="flex items-center justify-end gap-3">
      <button onClick={onToggle} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
        className="grid h-9 w-9 place-items-center rounded-full border border-[var(--border)] text-lg text-[var(--muted)] hover:text-[var(--accent)] hover:border-[var(--accent)] transition">
        {dark ? <Sun /> : <Moon />}
      </button>
      <span className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)] px-3.5 py-1.5 text-xs text-[var(--muted)]">
        <span className="h-2 w-2 rounded-full" style={{ background: youtube == null ? "var(--muted)" : youtube ? "var(--ok)" : "var(--warn)" }} />
        YouTube {youtube == null ? "..." : youtube ? "connected" : "not connected"}
      </span>
    </div>
  );
}
