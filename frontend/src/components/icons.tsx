import type { ReactNode, SVGProps } from "react";

const base = (p: SVGProps<SVGSVGElement>, children: ReactNode) => (
  <svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" strokeWidth="1.7"
       strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...p}>{children}</svg>
);
type P = SVGProps<SVGSVGElement>;

export const Logo = (p: P) => base(p, <><rect x="3" y="3" width="18" height="18" rx="5" /><path d="M10 8.5v7l5.5-3.5z" fill="currentColor" /></>);
export const Home = (p: P) => base(p, <path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />);
export const Film = (p: P) => base(p, <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4" /></>);
export const Scissors = (p: P) => base(p, <><circle cx="6" cy="6" r="3" /><circle cx="6" cy="18" r="3" /><path d="M20 4L8.1 15.9M14.5 14.5L20 20M8.1 8.1L12 12" /></>);
export const Gear = (p: P) => base(p, <><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" /></>);
export const Sun = (p: P) => base(p, <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>);
export const Moon = (p: P) => base(p, <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />);
export const Upload = (p: P) => base(p, <><path d="M7 18a5 5 0 1 1 1-9.9A6 6 0 0 1 19.5 10 4 4 0 0 1 18 18" /><path d="M12 12v8M9 15l3-3 3 3" /></>);
export const Play = (p: P) => base(p, <path d="M7 5l12 7-12 7z" fill="currentColor" />);
export const Pencil = (p: P) => base(p, <><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></>);
export const Refresh = (p: P) => base(p, <><path d="M21 12a9 9 0 0 1-15.5 6.3L3 16M3 12A9 9 0 0 1 18.5 5.7L21 8" /><path d="M21 3v5h-5M3 21v-5h5" /></>);
export const External = (p: P) => base(p, <><path d="M14 4h6v6M20 4l-9 9" /><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></>);
export const Clock = (p: P) => base(p, <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>);
export const Calendar = (p: P) => base(p, <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></>);
export const Check = (p: P) => base(p, <path d="M4 12.5l5 5L20 6.5" />);
export const Close = (p: P) => base(p, <path d="M6 6l12 12M18 6L6 18" />);
export const Chevron = (p: P) => base(p, <path d="M9 6l6 6-6 6" />);
export const Alert = (p: P) => base(p, <><path d="M12 3l10 18H2z" /><path d="M12 10v5M12 18h.01" /></>);
export const Doc = (p: P) => base(p, <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5M9 13h6M9 17h4" /></>);
