import { Chevron } from "./icons";

export function Pagination({ page, pages, onChange }: { page: number; pages: number; onChange: (p: number) => void }) {
  if (pages <= 1) return null;
  const btn = "grid h-9 min-w-9 place-items-center rounded-lg px-2 text-sm transition disabled:opacity-30 disabled:cursor-not-allowed";
  return (
    <nav aria-label="Pagination" className="mx-auto mt-6 flex w-fit items-center gap-1 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-1.5">
      <button className={`${btn} text-[var(--muted)] hover:text-[var(--text)]`} disabled={page === 1} onClick={() => onChange(page - 1)} aria-label="Previous page">
        <Chevron className="rotate-180" />
      </button>
      {Array.from({ length: pages }, (_, i) => i + 1).map((n) => (
        <button key={n} onClick={() => onChange(n)} aria-current={n === page ? "page" : undefined}
          className={`${btn} ${n === page ? "bg-[var(--accent)] text-[var(--accent-fg)] font-semibold" : "text-[var(--muted)] hover:text-[var(--text)]"}`}>{n}</button>
      ))}
      <button className={`${btn} text-[var(--muted)] hover:text-[var(--text)]`} disabled={page === pages} onClick={() => onChange(page + 1)} aria-label="Next page">
        <Chevron />
      </button>
    </nav>
  );
}
