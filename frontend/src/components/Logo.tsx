import clsx from "clsx";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={clsx("h-7 w-7", className)} aria-hidden>
      <rect width="32" height="32" rx="8" fill="#1B2A4A" />
      <path d="M10 9h12M10 16h9M10 23h12" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="23" cy="16" r="2.2" fill="#7DA2FF" />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={clsx("inline-flex items-center gap-2", className)}>
      <LogoMark />
      <span className="text-[16px] font-semibold tracking-tight text-ink">Evidra</span>
    </span>
  );
}
