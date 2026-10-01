import clsx from "clsx";
import {
  AlertOctagon,
  ArrowRight,
  BookOpen,
  Check,
  ClipboardCheck,
  EyeOff,
  FileSearch,
  FileStack,
  FlaskConical,
  Gavel,
  History,
  Layers,
  Link2,
  ListChecks,
  Scale,
  ShieldCheck,
  Upload,
  Users,
} from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Logo } from "../../components/Logo";
import { Badge, Button } from "../../components/ui";

export default function Landing() {
  return (
    <div className="bg-canvas">
      <header className="sticky top-0 z-30 border-b border-line/70 bg-canvas/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1200px] items-center gap-8 px-6">
          <Logo />
          <nav className="hidden items-center gap-6 text-[13.5px] text-muted md:flex">
            <a href="#how" className="hover:text-ink">How it works</a>
            <a href="#brief" className="hover:text-ink">Judge brief</a>
            <a href="#principles" className="hover:text-ink">Principles</a>
            <a href="#integrity" className="hover:text-ink">Integrity</a>
            <a href="#pilot" className="hover:text-ink">Pilot methodology</a>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Link to="/login">
              <Button variant="ghost" size="sm">Sign in</Button>
            </Link>
            <Link to="/login">
              <Button variant="primary" size="sm">Open the demo</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-[1200px] px-6 pb-16 pt-20 text-center">
        <Badge tone="neutral" className="mb-5">Judge copilot for hackathons &amp; innovation challenges</Badge>
        <h1 className="mx-auto max-w-4xl text-[44px] font-semibold leading-[1.08] tracking-[-0.02em] text-ink sm:text-[54px]">
          Let AI prepare the evidence.
          <br />
          <span className="text-[#44527a]">Let humans make the decision.</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-[17px] leading-relaxed text-muted">
          An AI-powered judge copilot that turns every hackathon submission into an evidence-backed evaluation brief.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3">
          <Link to="/login">
            <Button variant="primary" size="lg" icon={<ArrowRight className="h-4 w-4" />}>
              Explore the demo workspace
            </Button>
          </Link>
          <a href="#how">
            <Button variant="secondary" size="lg">How it works</Button>
          </a>
        </div>
        <Flow />
      </section>

      {/* 1. Problem */}
      <Section id="problem" eyebrow="01 · The problem" title="Hundreds of decks. Every one deserves a careful read.">
        <div className="grid gap-4 md:grid-cols-3">
          <Feature icon={<FileStack />} title="Volume">
            Innovation challenges can receive hundreds of PDF and PowerPoint submissions, each read by more than one judge.
          </Feature>
          <Feature icon={<ListChecks />} title="Repetition">
            For each one, judges locate the problem, the approach and the claims, check them against a rubric and write an assessment.
          </Feature>
          <Feature icon={<AlertOctagon />} title="Easy to miss">
            Unsupported numbers, unexplained dependencies and missing information are easy to overlook on the fortieth deck of the day.
          </Feature>
        </div>
      </Section>

      {/* 2. How it works */}
      <Section id="how" eyebrow="02 · How Evidra works" title="A small, inspectable pipeline — not an autonomous judge">
        <ol className="grid gap-px overflow-hidden rounded-2xl border border-line bg-line md:grid-cols-5">
          {[
            ["Ingestion", "Validates the file, extracts text and speaker notes, renders every slide and reads it back with OCR.", <Upload key="u" />],
            ["Evidence pack", "Each slide gets a stable ID. The AI receives this structured pack — never the raw file.", <Layers key="l" />],
            ["AI analysis", "Extractor → Rubric analyzer → Verifier → Brief generator. Every output is schema-validated JSON.", <FileSearch key="f" />],
            ["Judge brief", "Overview, evidence, strengths, Verify These and Not Assessed — every finding linked to its slide.", <BookOpen key="b" />],
            ["Human decision", "Judges score independently. The AI score stays hidden until they submit.", <Gavel key="g" />],
          ].map(([title, body, icon], i) => (
            <li key={String(title)} className="bg-surface p-5">
              <div className="flex items-center gap-2 text-muted">
                <span className="[&>svg]:h-4 [&>svg]:w-4">{icon}</span>
                <span className="tabular text-[12px]">Step {i + 1}</span>
              </div>
              <div className="mt-3 text-[15px] font-semibold text-ink">{title}</div>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{body}</p>
            </li>
          ))}
        </ol>
      </Section>

      {/* 3. Brief demo */}
      <Section id="brief" eyebrow="03 · The judge brief" title="The evidence that deserves a judge’s attention — linked to the exact slide">
        <BriefDemo />
      </Section>

      {/* 4. Human in the loop */}
      <Section id="principles" eyebrow="04 · Human-in-the-loop by design" title="The human decision is the only decision">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Feature icon={<EyeOff />} title="AI score hidden first">
            Judges score independently. The AI's preliminary assessment is released by the server only after the judge submits.
          </Feature>
          <Feature icon={<Scale />} title="Keep or revise">
            After the reveal, judges keep their score or revise it with a reason. Both versions are recorded.
          </Feature>
          <Feature icon={<ClipboardCheck />} title="Disagree with anything">
            Every strength and every Verify These item can be marked agree, disagree or unsure — with a note.
          </Feature>
          <Feature icon={<Users />} title="Every submission, human-reviewed">
            No automatic rejection, no automatic winners, no public leaderboard. Results are never ranked by the AI.
          </Feature>
        </div>
      </Section>

      {/* 5. Evidence */}
      <Section id="evidence" eyebrow="05 · Evidence-backed evaluation" title="No finding without a source">
        <div className="grid items-start gap-8 lg:grid-cols-2">
          <ul className="space-y-4 text-[14.5px] text-ink-2">
            <Bullet>Every important finding cites a slide ID and a verbatim excerpt; the excerpt is checked against the slide, and excerpts that don't match are marked as such.</Bullet>
            <Bullet>Findings that point to slides that don't exist are dropped automatically rather than displayed without a source.</Bullet>
            <Bullet>If something could not be processed — an image-only slide, an external video link, a rendering failure — the brief says “Not assessed” instead of guessing.</Bullet>
            <Bullet>If the AI step fails, judges see “AI analysis unavailable. Human review can continue.” Nothing is fabricated.</Bullet>
          </ul>
          <div className="rounded-2xl border border-line bg-surface p-5 font-mono text-[12px] leading-relaxed text-ink-2 shadow-card">
            <div className="mb-2 text-[11px] uppercase tracking-wider text-faint">Structured finding</div>
            <pre className="whitespace-pre-wrap">{`{
  "criterion": "Impact",
  "finding": "Impact figures are stated without supporting data.",
  "evidence": [
    { "slide_id": "slide_07",
      "excerpt": "40% reduction in collection costs." }
  ],
  "issues": [
    { "type": "unsupported_claim",
      "severity": "high" }
  ]
}`}</pre>
          </div>
        </div>
      </Section>

      {/* 6. Integrity */}
      <Section id="integrity" eyebrow="06 · Integrity checks" title="Checks for hidden content — described with appropriate caution">
        <div className="grid gap-4 md:grid-cols-3">
          <Feature icon={<Layers />} title="Text layer vs. rendered slide">
            Extracted text is fuzzy-matched against OCR of the rendered slide to find text a human would not see, such as white-on-white or off-slide text.
          </Feature>
          <Feature icon={<ShieldCheck />} title="Only instruction-like text escalates">
            Mismatches are not treated as malicious. Hidden text that resembles an instruction to evaluators is flagged and withheld from AI analysis.
          </Feature>
          <Feature icon={<AlertOctagon />} title="Honest limits">
            We report “No hidden-content discrepancy detected” — never “clean”. Visible persuasive text is not an injection, and no check detects every manipulation.
          </Feature>
        </div>
      </Section>

      {/* 7. Organizer workflow */}
      <Section id="organizer" eyebrow="07 · Organizer workflow" title="From call for submissions to calibrated results">
        <div className="grid gap-px overflow-hidden rounded-2xl border border-line bg-line md:grid-cols-3">
          {[
            ["Define the round", "Name, description, weighted rubric, file limits and judges per submission."],
            ["Upload & process", "Drop in PDFs and PPTX files; watch each move through validation, rendering, OCR, integrity and analysis."],
            ["Assign judges", "Balanced auto-assignment or a simple matrix. Started reviews are protected."],
            ["Track progress", "Processed, awaiting review, in review, completed — plus integrity warnings and processing failures."],
            ["Review results", "Human scores per submission, judge disagreement, and revision data — listed alphabetically, never ranked."],
            ["Audit everything", "Uploads, processing, reveals, revisions and responses to AI findings are all recorded."],
          ].map(([t, b]) => (
            <div key={t} className="bg-surface p-5">
              <div className="flex items-center gap-2 text-[14.5px] font-semibold">
                <Check className="h-4 w-4 text-ok" /> {t}
              </div>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{b}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* 8. Pilot methodology */}
      <Section id="pilot" eyebrow="08 · Pilot evaluation methodology" title="Designed to reduce repetitive judging work while preserving human decision-making">
        <div className="grid gap-8 lg:grid-cols-[1.2fr_1fr]">
          <div className="text-[14.5px] leading-relaxed text-ink-2">
            <p>
              We have not yet run a controlled evaluation, so we make no performance claims. Our pilot will compare judging with and without Evidra on the same set of submissions and
              will measure:
            </p>
            <ul className="mt-4 grid gap-2 sm:grid-cols-2">
              {["Review time per submission", "Shortlist / decision agreement", "Issues missed by judges", "Usefulness of “Verify These”", "Human revisions after AI reveal"].map((m) => (
                <li key={m} className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-[13.5px]">
                  <FlaskConical className="h-4 w-4 text-muted" /> {m}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl border border-line bg-surface p-5 text-[13.5px] leading-relaxed text-ink-2 shadow-card">
            <div className="flex items-center gap-2 font-semibold text-ink">
              <History className="h-4 w-4 text-muted" /> Anchoring data, recorded by default
            </div>
            <p className="mt-2 text-muted">
              For every evaluation we store the judge's initial score, the AI score, the revised score, the reason and the timestamps — and compute the direction of any revision.
              These are descriptive data for later analysis; on their own they do not prove anchoring.
            </p>
          </div>
        </div>
      </Section>

      <section className="mx-auto max-w-[1200px] px-6 pb-24">
        <div className="flex flex-col items-center gap-4 rounded-2xl bg-navy px-8 py-12 text-center text-white">
          <h2 className="text-[26px] font-semibold tracking-tight">See the judge workflow end to end</h2>
          <p className="max-w-xl text-[14.5px] text-white/75">The demo workspace contains six fictional submissions, including an integrity warning, a partially assessed deck and a failed upload.</p>
          <Link to="/login">
            <Button size="lg" className="bg-white text-navy hover:bg-white/90" icon={<ArrowRight className="h-4 w-4" />}>
              Open the demo
            </Button>
          </Link>
        </div>
      </section>

      <footer className="border-t border-line py-8 text-center text-[12.5px] text-faint">
        Evidra · Evidence-backed judging with humans in charge · V1 supports PDF and PPTX submissions
      </footer>
    </div>
  );
}

function Flow() {
  const steps = [
    { label: "PPT / PDF", icon: <FileStack className="h-4 w-4" /> },
    { label: "Evidence", icon: <Layers className="h-4 w-4" /> },
    { label: "Verify", icon: <ListChecks className="h-4 w-4" /> },
    { label: "Human decision", icon: <Gavel className="h-4 w-4" />, strong: true },
  ];
  return (
    <div className="mx-auto mt-14 flex max-w-3xl flex-wrap items-center justify-center gap-2">
      {steps.map((s, i) => (
        <div key={s.label} className="flex items-center gap-2">
          <div
            className={clsx(
              "flex items-center gap-2 rounded-xl border px-4 py-2.5 text-[14px] font-medium shadow-card",
              s.strong ? "border-navy bg-navy text-white" : "border-line bg-surface text-ink",
            )}
          >
            {s.icon}
            {s.label}
          </div>
          {i < steps.length - 1 && <ArrowRight className="h-4 w-4 text-faint" />}
        </div>
      ))}
    </div>
  );
}

function Section({ id, eyebrow, title, children }: { id: string; eyebrow: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="mx-auto max-w-[1200px] scroll-mt-16 px-6 py-16">
      <div className="eyebrow">{eyebrow}</div>
      <h2 className="mb-8 mt-2 max-w-3xl text-[28px] font-semibold leading-tight tracking-tight">{title}</h2>
      {children}
    </section>
  );
}

function Feature({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-5 shadow-card">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sunken text-ink-2 [&>svg]:h-4 [&>svg]:w-4">{icon}</div>
      <div className="mt-3 text-[15px] font-semibold">{title}</div>
      <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted">{children}</p>
    </div>
  );
}

function Bullet({ children }: { children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <Check className="mt-1 h-4 w-4 shrink-0 text-ok" />
      <span>{children}</span>
    </li>
  );
}

function SlideTag({ n }: { n: number }) {
  return <span className="inline-flex items-center gap-1 rounded-md border border-[#d6e0fb] bg-accent-soft px-1.5 py-0.5 text-[12px] font-medium text-accent-strong">View Slide {n}</span>;
}

function BriefDemo() {
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.35fr]">
      <div className="space-y-3 text-[14px] text-ink-2">
        <p className="leading-relaxed">
          The brief is the centre of Evidra. It sits next to the original deck, so a judge can click <SlideTag n={6} /> and the viewer jumps straight to the slide, with the cited passage
          highlighted.
        </p>
        <ul className="space-y-2 pt-2">
          {[
            ["Verify these", "Source-linked findings that deserve human attention — first, by priority"],
            ["Submission overview", "What is the team proposing?"],
            ["Strengths", "Concrete positive findings"],
            ["Not assessed", "What the system could not inspect"],
            ["Submission integrity", "Potential hidden or inconsistent content"],
            ["Evidence map", "Key elements of the proposal, linked to slides"],
          ].map(([t, d]) => (
            <li key={t} className="flex gap-2">
              <Link2 className="mt-1 h-3.5 w-3.5 shrink-0 text-faint" />
              <span>
                <span className="font-medium text-ink">{t}</span> — {d}
              </span>
            </li>
          ))}
        </ul>
        <p className="pt-2 text-[12.5px] text-faint">Illustrative example based on a fictional submission.</p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-line bg-canvas shadow-pop">
        <div className="flex items-center justify-between border-b border-line bg-surface px-4 py-2.5">
          <div>
            <div className="text-[13.5px] font-semibold">BinSight — Route Zero</div>
            <div className="text-[11.5px] text-muted">Judge brief · AI score hidden until you submit</div>
          </div>
          <Badge tone="ok" icon={<ShieldCheck className="h-3 w-3" />}>Integrity check: no issue detected</Badge>
        </div>
        <div className="space-y-3 p-4 text-[13px]">
          <DemoCard title="Submission overview">
            Team proposes an AI-based waste collection optimization platform for municipalities.
          </DemoCard>
          <DemoCard title="Verify these" strong>
            <ol className="space-y-2.5">
              <DemoVerify n={1} title="Claimed 40% cost reduction" sev="High priority" slide={7}>
                No supporting experiment or benchmark was found.
              </DemoVerify>
              <DemoVerify n={2} title="Technical feasibility" sev="Medium priority" slide={6}>
                The proposal depends on a hardware assumption that is not explained.
              </DemoVerify>
              <DemoVerify n={3} title="Differentiation" sev="Medium priority">
                Potentially similar approaches may exist. <span className="italic text-warn">Potential similarity — human verification required.</span>
              </DemoVerify>
            </ol>
          </DemoCard>
          <DemoCard title="Evidence">
            <div className="grid grid-cols-[130px_1fr] gap-y-1.5">
              <span className="font-medium">Problem definition</span>
              <span><SlideTag n={2} /></span>
              <span className="font-medium">Architecture</span>
              <span><SlideTag n={5} /></span>
              <span className="font-medium">Expected impact</span>
              <span><SlideTag n={7} /></span>
            </div>
          </DemoCard>
          <DemoCard title="Not assessed">External content linked on Slide 9 could not be accessed.</DemoCard>
        </div>
      </div>
    </div>
  );
}

function DemoCard({ title, children, strong }: { title: string; children: ReactNode; strong?: boolean }) {
  return (
    <div className={clsx("rounded-xl border bg-surface p-3.5", strong ? "border-line-strong" : "border-line")}>
      <div className="mb-1.5 text-[12px] font-semibold uppercase tracking-wide text-faint">{title}</div>
      <div className="text-ink-2">{children}</div>
    </div>
  );
}

function DemoVerify({ n, title, sev, slide, children }: { n: number; title: string; sev: string; slide?: number; children: ReactNode }) {
  return (
    <li className="flex gap-2.5">
      <span className="tabular mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-navy text-[11px] font-semibold text-white">{n}</span>
      <div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-semibold text-ink">{title}</span>
          <Badge tone={sev.startsWith("High") ? "navy" : "accent"}>{sev}</Badge>
        </div>
        <p className="mt-0.5">{children}</p>
        {slide && <div className="mt-1"><SlideTag n={slide} /></div>}
      </div>
    </li>
  );
}
