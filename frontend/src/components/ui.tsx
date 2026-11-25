import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "outline" | "ghost";
const styles: Record<Variant, string> = {
  primary: "bg-[var(--accent)] text-[var(--accent-fg)] hover:brightness-110 border border-transparent",
  outline: "border border-[var(--border)] text-[var(--text)] hover:border-[var(--accent)] hover:text-[var(--accent)] bg-transparent",
  ghost: "text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] border border-transparent",
};
const disabledCls = "disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:brightness-100 disabled:hover:border-[var(--border)] disabled:hover:text-[var(--text)]";

export function Button({ variant = "outline", className = "", ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button {...p}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition ${disabledCls} ${styles[variant]} ${className}`} />
  );
}

export function Chip({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1 text-xs text-[var(--muted)]">
      {icon}{children}
    </span>
  );
}
