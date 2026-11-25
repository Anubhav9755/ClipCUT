import type { ReactNode } from "react";
import { Film, Gear, Home, Logo, Scissors } from "./icons";

function Item({ icon, label, active, disabled }: { icon: ReactNode; label: string; active?: boolean; disabled?: boolean }) {
  return (
    <div role="link" aria-disabled={disabled || undefined} aria-current={active ? "page" : undefined}
      title={disabled ? `${label} (coming soon)` : label}
      className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition border
        ${active ? "bg-[var(--surface-2)] text-[var(--accent)] border-[var(--border)]"
          : disabled ? "text-[var(--muted)] opacity-45 cursor-not-allowed border-transparent"
          : "text-[var(--muted)] hover:text-[var(--text)] border-transparent"}`}>
      <span className="text-xl shrink-0">{icon}</span>
      <span className="hidden lg:inline">{label}</span>
    </div>
  );
}

export function Dot({ state, on, off }: { state: boolean | null; on: string; off: string }) {
  const color = state == null ? "var(--muted)" : state ? "var(--ok)" : "var(--warn)";
  return (
    <div className="flex items-center gap-2">
      <span className="h-2 w-2 rounded-full shrink-0" style={{ background: color }} />
      <span>{state == null ? "Checking..." : state ? on : off}</span>
    </div>
  );
}

export function Sidebar({ aiKey, youtube }: { aiKey: boolean | null; youtube: boolean | null }) {
  return (
    <aside className="flex w-16 lg:w-60 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] px-2 lg:px-4 py-5">
      <div className="mb-8 flex items-center gap-2.5 px-2 text-[var(--text)]">
        <Logo className="text-3xl text-[var(--accent)] shrink-0" />
        <span className="hidden lg:inline text-lg font-semibold tracking-tight">ClipCUT</span>
      </div>
      <nav className="flex flex-col gap-1" aria-label="Main">
        <Item icon={<Home />} label="Dashboard" disabled />
        <Item icon={<Film />} label="Episodes" active />
        <Item icon={<Scissors />} label="Video Editor" disabled />
        <Item icon={<Gear />} label="Settings" disabled />
      </nav>
      <div className="mt-auto hidden lg:block rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-3 text-xs text-[var(--muted)] space-y-2">
        <Dot state={aiKey} on="AI picker active" off="AI key missing: basic picker" />
        <Dot state={youtube} on="YouTube connected" off="YouTube not connected" />
      </div>
    </aside>
  );
}
