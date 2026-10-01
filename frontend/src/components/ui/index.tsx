import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Info, Loader2, ShieldAlert, ShieldCheck, X } from "lucide-react";
import { forwardRef, useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";
import { INTEGRITY_HINT, INTEGRITY_LABEL } from "../../lib/format";
import type { IntegrityStatus } from "../../lib/types";

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------

type Variant = "primary" | "secondary" | "ghost" | "danger" | "subtle";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-navy text-white hover:bg-[#23365e] shadow-sm disabled:bg-navy/40",
  secondary: "bg-surface text-ink border border-line-strong hover:bg-sunken shadow-card disabled:text-faint",
  ghost: "text-ink-2 hover:bg-sunken hover:text-ink disabled:text-faint",
  subtle: "bg-accent-soft text-accent-strong hover:bg-[#e2e9fc] disabled:opacity-50",
  danger: "bg-danger text-white hover:bg-[#9c1e14] disabled:opacity-50",
};
const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-9 px-3.5 text-sm gap-2",
  lg: "h-11 px-5 text-[15px] gap-2",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", loading, icon, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex select-none items-center justify-center whitespace-nowrap rounded-lg font-medium transition-colors disabled:cursor-not-allowed",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
});

// ---------------------------------------------------------------------------
// Layout primitives
// ---------------------------------------------------------------------------

export function Card({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={clsx("rounded-xl border border-line bg-surface shadow-card", className)} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action, className }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={clsx("flex items-start justify-between gap-4 border-b border-line px-5 py-4", className)}>
      <div className="min-w-0">
        <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
        {subtitle && <p className="mt-0.5 text-[13px] text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: ReactNode; title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-[14px] text-muted">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={clsx("h-4 w-4 animate-spin text-muted", className)} />;
}

export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-20 text-sm text-muted">
      <Spinner /> {label}
    </div>
  );
}

export function ErrorBlock({ error }: { error: unknown }) {
  return (
    <Callout tone="danger" title="Something went wrong">
      {error instanceof Error ? error.message : String(error)}
    </Callout>
  );
}

export function EmptyState({ icon, title, description, action }: { icon?: ReactNode; title: string; description?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      {icon && <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-sunken text-muted">{icon}</div>}
      <div className="text-[15px] font-medium text-ink">{title}</div>
      {description && <p className="mt-1 max-w-md text-[13px] text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Badges & callouts
// ---------------------------------------------------------------------------

type Tone = "neutral" | "accent" | "ok" | "warn" | "danger" | "navy";
const TONES: Record<Tone, string> = {
  neutral: "bg-sunken text-ink-2 ring-line",
  accent: "bg-accent-soft text-accent-strong ring-[#d6e0fb]",
  ok: "bg-ok-soft text-ok ring-[#c9ead8]",
  warn: "bg-warn-soft text-warn ring-warn-line",
  danger: "bg-danger-soft text-danger ring-danger-line",
  navy: "bg-navy text-white ring-navy",
};

export function Badge({ tone = "neutral", children, className, icon }: { tone?: Tone; children: ReactNode; className?: string; icon?: ReactNode }) {
  return (
    <span className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11.5px] font-medium ring-1 ring-inset", TONES[tone], className)}>
      {icon}
      {children}
    </span>
  );
}

export function Dot({ tone = "neutral" }: { tone?: Tone }) {
  const color = { neutral: "bg-faint", accent: "bg-accent", ok: "bg-ok", warn: "bg-[#d98b1c]", danger: "bg-danger", navy: "bg-navy" }[tone];
  return <span className={clsx("inline-block h-1.5 w-1.5 shrink-0 rounded-full", color)} />;
}

export function integrityTone(status: IntegrityStatus | null | undefined): Tone {
  if (!status || status === "no_discrepancy_detected") return "ok";
  if (status === "suspicious_instruction_detected") return "danger";
  return "warn";
}

/**
 * Integrity / ingestion status of a submission. Wording refers only to the check,
 * never to the merit of the submission.
 *  - processing failed            → "Manual review required"
 *  - hidden / inconsistent text   → "Integrity review required"
 *  - check passed                 → "Integrity check: no issue detected"
 * Pass `notAssessedCount` / `submissionStatus` to also show "Partially assessed".
 */
export function IntegrityBadge({
  status,
  submissionStatus,
  notAssessedCount = 0,
}: {
  status: IntegrityStatus | null | undefined;
  submissionStatus?: string | null;
  notAssessedCount?: number;
}) {
  if (submissionStatus === "processing_failed") {
    return (
      <Badge tone="danger" icon={<ShieldAlert className="h-3 w-3" />}>
        <span title="The document could not be fully processed. A human must review the original file.">Manual review required</span>
      </Badge>
    );
  }
  const partial = submissionStatus === "partially_processed" || notAssessedCount > 0;
  const tone = integrityTone(status);
  const Icon = tone === "ok" ? ShieldCheck : ShieldAlert;
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {status ? (
        <Badge tone={tone} icon={<Icon className="h-3 w-3" />}>
          <span title={INTEGRITY_HINT[status]}>{INTEGRITY_LABEL[status]}</span>
        </Badge>
      ) : (
        <Badge>Integrity not checked</Badge>
      )}
      {partial && (
        <Badge tone="neutral">
          <span title="Some material could not be reliably evaluated (e.g. image-only content, external links, rendering issues).">Partially assessed</span>
        </Badge>
      )}
    </span>
  );
}

export function Callout({ tone = "neutral", title, children, className, icon }: { tone?: "neutral" | "accent" | "warn" | "danger" | "ok"; title?: ReactNode; children?: ReactNode; className?: string; icon?: ReactNode }) {
  const styles = {
    neutral: "bg-sunken border-line text-ink-2",
    accent: "bg-accent-soft border-[#d6e0fb] text-[#233a86]",
    warn: "bg-warn-soft border-warn-line text-[#6f3b06]",
    danger: "bg-danger-soft border-danger-line text-[#7a1a12]",
    ok: "bg-ok-soft border-[#c9ead8] text-[#0b5535]",
  }[tone];
  const DefaultIcon = { neutral: Info, accent: Info, warn: AlertTriangle, danger: AlertTriangle, ok: CheckCircle2 }[tone];
  return (
    <div className={clsx("flex gap-3 rounded-lg border px-3.5 py-3 text-[13px]", styles, className)}>
      <span className="mt-0.5 shrink-0">{icon ?? <DefaultIcon className="h-4 w-4" />}</span>
      <div className="min-w-0">
        {title && <div className="font-semibold">{title}</div>}
        {children && <div className={clsx(title && "mt-0.5", "leading-relaxed")}>{children}</div>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Data display
// ---------------------------------------------------------------------------

export function Stat({ label, value, hint, tone, icon }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "warn" | "danger" | "ok"; icon?: ReactNode }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <span className="text-[12.5px] font-medium text-muted">{label}</span>
        {icon && <span className="text-faint">{icon}</span>}
      </div>
      <div
        className={clsx(
          "tabular mt-2 text-[26px] font-semibold leading-none tracking-tight",
          tone === "warn" ? "text-warn" : tone === "danger" ? "text-danger" : tone === "ok" ? "text-ok" : "text-ink",
        )}
      >
        {value}
      </div>
      {hint && <div className="mt-2 text-[12px] text-muted">{hint}</div>}
    </Card>
  );
}

export function ProgressBar({ value, className, tone = "navy" }: { value: number; className?: string; tone?: "navy" | "ok" | "accent" }) {
  const color = { navy: "bg-navy", ok: "bg-ok", accent: "bg-accent" }[tone];
  return (
    <div className={clsx("h-1.5 w-full overflow-hidden rounded-full bg-sunken", className)}>
      <div className={clsx("h-full rounded-full transition-all duration-500", color)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="rounded border border-line bg-surface px-1 font-mono text-[10.5px] text-muted">{children}</kbd>;
}

// ---------------------------------------------------------------------------
// Dialog
// ---------------------------------------------------------------------------

export function Dialog({ open, onClose, title, children, footer, width = "max-w-lg" }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; width?: string }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="animate-fade-in absolute inset-0 bg-ink/30 backdrop-blur-[1px]" onClick={onClose} />
      <div role="dialog" aria-modal="true" className={clsx("animate-slide-up relative w-full rounded-xl border border-line bg-surface shadow-pop", width)}>
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h2 className="text-[15px] font-semibold">{title}</h2>
          <button onClick={onClose} className="rounded-md p-1 text-muted hover:bg-sunken" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line bg-canvas/60 px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Segmented score picker
// ---------------------------------------------------------------------------

export function ScorePicker({ max, value, onChange, disabled, compareValue }: { max: number; value: number | null; onChange: (v: number) => void; disabled?: boolean; compareValue?: number | null }) {
  const values = Array.from({ length: max }, (_, i) => i + 1);
  return (
    <div className="flex gap-1" role="radiogroup">
      {values.map((v) => {
        const selected = value === v;
        const isCompare = compareValue !== undefined && compareValue !== null && Math.round(compareValue) === v;
        return (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange(v)}
            className={clsx(
              "tabular relative h-8 min-w-0 flex-1 rounded-md border text-[13px] font-medium transition-all",
              selected
                ? "border-navy bg-navy text-white shadow-sm"
                : "border-line bg-surface text-ink-2 hover:border-line-strong hover:bg-sunken",
              disabled && !selected && "opacity-60 hover:bg-surface",
              disabled && "cursor-not-allowed",
            )}
          >
            {v}
            {isCompare && !selected && <span className="absolute -top-1 right-0.5 h-1.5 w-1.5 rounded-full bg-accent" />}
          </button>
        );
      })}
    </div>
  );
}
