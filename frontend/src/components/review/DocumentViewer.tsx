import clsx from "clsx";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  FileText,
  ImageOff,
  Link2,
  Quote,
  StickyNote,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { authUrl } from "../../lib/api";
import type { DocumentInfo, SlideInfo } from "../../lib/types";
import { Badge, Callout, Kbd } from "../ui";

export interface ViewerFocus {
  slideId: string;
  excerpt?: string;
  nonce: number;
}

type Panel = "text" | "notes" | "integrity" | null;

export function DocumentViewer({
  document: doc,
  current,
  onChange,
  focus,
  onClearFocus,
}: {
  document: DocumentInfo;
  current: number;
  onChange: (index: number) => void;
  focus: ViewerFocus | null;
  onClearFocus: () => void;
}) {
  const slides = doc.slides;
  const slide: SlideInfo | undefined = slides[current];
  const [panel, setPanel] = useState<Panel>(null);
  const [loaded, setLoaded] = useState<Record<number, boolean>>({});
  const stripRef = useRef<HTMLDivElement>(null);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) || t.isContentEditable) return;
      if (e.key === "ArrowRight" && current < slides.length - 1) onChange(current + 1);
      if (e.key === "ArrowLeft" && current > 0) onChange(current - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [current, slides.length, onChange]);

  useEffect(() => {
    const el = stripRef.current?.querySelector<HTMLElement>(`[data-index="${current}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [current]);

  useEffect(() => {
    if (!focus) return;
    setFlash(true);
    const t = setTimeout(() => setFlash(false), 900);
    return () => clearTimeout(t);
  }, [focus?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!slides.length) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-sunken p-8 text-center">
        <FileText className="h-8 w-8 text-faint" />
        <div className="max-w-sm">
          <div className="font-medium text-ink">{doc.processing.message ?? "No pages available"}</div>
          {doc.processing.error && <p className="mt-1 text-[13px] text-muted">{doc.processing.error}</p>}
        </div>
        {doc.file && (
          <a href={authUrl(`${doc.file.download_url}?download=1`)} className="text-[13px] font-medium text-accent hover:underline">
            Download original file ({doc.file.name})
          </a>
        )}
      </div>
    );
  }

  const flags = slide?.integrity_flags.filter((f) => f.status !== "no_discrepancy_detected") ?? [];
  const focusHere = focus && slide && focus.slideId === slide.slide_key && focus.excerpt;

  return (
    <div className="flex h-full min-h-0 flex-col bg-[#ecebe7]">
      {/* toolbar */}
      <div className="flex h-11 shrink-0 items-center gap-2 border-b border-line bg-surface px-3">
        <FileText className="h-4 w-4 text-muted" />
        <span className="truncate text-[13px] font-medium text-ink" title={doc.file?.name}>
          {doc.file?.name}
        </span>
        <Badge className="uppercase">{doc.file?.type}</Badge>
        <div className="ml-auto flex items-center gap-1">
          <button
            className="rounded-md p-1.5 text-muted hover:bg-sunken disabled:opacity-40"
            disabled={current === 0}
            onClick={() => onChange(current - 1)}
            aria-label="Previous slide"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="tabular min-w-[74px] text-center text-[13px] text-ink-2">
            Slide {slide?.page_number} <span className="text-faint">/ {slides.length}</span>
          </span>
          <button
            className="rounded-md p-1.5 text-muted hover:bg-sunken disabled:opacity-40"
            disabled={current >= slides.length - 1}
            onClick={() => onChange(current + 1)}
            aria-label="Next slide"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          {doc.file && (
            <a
              href={authUrl(doc.file.type === "pdf" ? doc.file.download_url : `${doc.file.download_url}?download=1`)}
              target="_blank"
              rel="noreferrer"
              className="ml-2 inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-[12px] font-medium text-ink-2 hover:bg-sunken"
            >
              Original <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </div>

      {/* stage */}
      <div className="relative min-h-0 flex-1 overflow-auto p-4">
        {slide?.image_url ? (
          <div className="flex h-full min-h-[240px] items-center justify-center">
            <img
              key={slide.id}
              src={authUrl(slide.image_url)}
              alt={`Slide ${slide.page_number}${slide.title ? `: ${slide.title}` : ""}`}
              onLoad={() => setLoaded((s) => ({ ...s, [slide.id]: true }))}
              className={clsx(
                "max-h-full max-w-full rounded-md bg-white shadow-[0_2px_12px_rgba(20,23,31,0.12)] transition-all duration-300",
                loaded[slide.id] ? "opacity-100" : "opacity-0",
                flash && "ring-4 ring-accent/40",
              )}
            />
          </div>
        ) : (
          <div className="mx-auto flex h-full max-w-2xl flex-col justify-center">
            <div className="rounded-md border border-line bg-surface p-6 shadow-card">
              <div className="mb-3 flex items-center gap-2 text-[12.5px] text-muted">
                <ImageOff className="h-4 w-4" /> Slide preview unavailable — showing extracted text
              </div>
              <div className="text-[15px] font-semibold">{slide?.title}</div>
              <pre className="mt-2 whitespace-pre-wrap font-sans text-[13.5px] leading-relaxed text-ink-2">{slide?.text || "No text extracted."}</pre>
              {slide?.processing_notes.map((n) => (
                <p key={n} className="mt-3 text-[12px] text-muted">{n}</p>
              ))}
            </div>
          </div>
        )}

        {focusHere && (
          <div className="animate-slide-up absolute inset-x-4 bottom-4 mx-auto max-w-2xl">
            <div className="flex items-start gap-2.5 rounded-lg border border-[#d6e0fb] bg-surface/95 px-3.5 py-2.5 shadow-pop backdrop-blur">
              <Quote className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
              <div className="min-w-0 text-[13px]">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-accent">Cited on Slide {slide?.page_number}</div>
                <div className="mt-0.5 text-ink-2">“{focus.excerpt}”</div>
              </div>
              <button onClick={onClearFocus} className="ml-auto rounded p-0.5 text-muted hover:bg-sunken" aria-label="Dismiss">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* thumbnails */}
      <div ref={stripRef} className="scroll-thin flex shrink-0 gap-2 overflow-x-auto border-t border-line bg-surface px-3 py-2">
        {slides.map((s, i) => {
          const warn = s.integrity_flags.some((f) => f.status !== "no_discrepancy_detected");
          return (
            <button
              key={s.id}
              data-index={i}
              onClick={() => onChange(i)}
              className={clsx(
                "group relative shrink-0 overflow-hidden rounded border-2 transition-colors",
                i === current ? "border-navy" : "border-transparent hover:border-line-strong",
              )}
              title={`Slide ${s.page_number}${s.title ? ` — ${s.title}` : ""}`}
            >
              {s.thumb_url ? (
                <img src={authUrl(s.thumb_url)} alt="" className="h-[46px] w-[82px] bg-white object-cover" loading="lazy" />
              ) : (
                <div className="flex h-[46px] w-[82px] items-center justify-center bg-sunken text-[10px] text-muted">No preview</div>
              )}
              <span className="tabular absolute bottom-0 left-0 rounded-tr bg-ink/70 px-1 text-[10px] font-medium text-white">{s.page_number}</span>
              {warn && <span className="absolute right-0.5 top-0.5 h-2 w-2 rounded-full bg-[#d98b1c] ring-2 ring-white" />}
            </button>
          );
        })}
      </div>

      {/* inspector */}
      <div className="shrink-0 border-t border-line bg-surface">
        <div className="flex items-center gap-1 px-2 py-1.5">
          <InspectorTab active={panel === "text"} onClick={() => setPanel(panel === "text" ? null : "text")} icon={<FileText className="h-3.5 w-3.5" />}>
            Extracted text
          </InspectorTab>
          <InspectorTab
            active={panel === "notes"}
            onClick={() => setPanel(panel === "notes" ? null : "notes")}
            icon={<StickyNote className="h-3.5 w-3.5" />}
            disabled={doc.file?.type !== "pptx"}
          >
            Speaker notes{slide?.speaker_notes ? " ·" : ""}
          </InspectorTab>
          <InspectorTab
            active={panel === "integrity"}
            onClick={() => setPanel(panel === "integrity" ? null : "integrity")}
            icon={<AlertTriangle className={clsx("h-3.5 w-3.5", flags.length && "text-warn")} />}
          >
            Integrity{flags.length ? ` (${flags.length})` : ""}
          </InspectorTab>
          {slide && slide.links.length > 0 && (
            <span className="ml-1 inline-flex items-center gap-1 text-[12px] text-muted" title={slide.links.join("\n")}>
              <Link2 className="h-3.5 w-3.5" /> {slide.links.length} external link{slide.links.length > 1 ? "s" : ""} (not followed)
            </span>
          )}
          <span className="ml-auto hidden items-center gap-1 text-[11px] text-faint xl:flex">
            <Kbd>←</Kbd>
            <Kbd>→</Kbd> to navigate
          </span>
        </div>
        {panel && slide && (
          <div className="scroll-thin max-h-[200px] overflow-y-auto border-t border-line px-4 py-3 text-[13px]">
            {panel === "text" && (
              <>
                <pre className="whitespace-pre-wrap font-sans leading-relaxed text-ink-2">{slide.text || "No text layer on this slide."}</pre>
                {slide.ocr_text && slide.has_visual_content && (
                  <div className="mt-3 border-t border-line pt-3">
                    <div className="eyebrow mb-1">Text read from images (OCR)</div>
                    <pre className="whitespace-pre-wrap font-sans leading-relaxed text-muted">{slide.ocr_text}</pre>
                  </div>
                )}
              </>
            )}
            {panel === "notes" && (
              <pre className="whitespace-pre-wrap font-sans leading-relaxed text-ink-2">{slide.speaker_notes || "No speaker notes on this slide."}</pre>
            )}
            {panel === "integrity" &&
              (slide.integrity_flags.length === 0 ? (
                <p className="text-muted">No integrity observations on this slide. The check cannot rule out every form of manipulation.</p>
              ) : (
                <div className="space-y-2">
                  {slide.integrity_flags.map((f, i) => (
                    <Callout key={i} tone={f.status === "no_discrepancy_detected" ? "neutral" : f.status === "suspicious_instruction_detected" ? "danger" : "warn"}>
                      <div>{f.detail}</div>
                      {f.excerpt && <div className="mt-1 font-mono text-[12px] opacity-90">“{f.excerpt}”</div>}
                      <div className="mt-1 text-[11.5px] opacity-75">
                        Location: {f.location.replace("_", " ")}
                        {f.withheld_from_ai && " · withheld from AI analysis"}
                      </div>
                    </Callout>
                  ))}
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}

function InspectorTab({ active, onClick, icon, children, disabled }: { active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[12.5px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40",
        active ? "bg-sunken text-ink" : "text-muted hover:text-ink",
      )}
    >
      {icon}
      {children}
    </button>
  );
}
