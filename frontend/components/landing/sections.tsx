"use client";

import React, { useEffect, useState } from "react";
import { ChevronDown, Play, Search, X } from "lucide-react";
import ThemeToggle from "../ThemeToggle";
import {
  Arrow,
  BookCream,
  BookGreen,
  BookMaroon,
  CoverAgents,
  CoverBioactivity,
  CoverBriefing,
  CoverCompound,
  CoverLiterature,
  CoverMolecule,
  CoverProperties,
  CoverTrials,
  IconActivity,
  IconBriefing,
  IconExport,
  IconListen,
  IconMolecule,
  IconRefine,
  IconSearch,
  IconSources,
  LogoMark,
} from "./art";

export interface LandingActions {
  onStart: () => void;
  onLaunch: (query?: string) => void;
  onOpenKeys: () => void;
}

const DEMO_QUERY = "Find novel small molecules related to EGFR target and explain why each candidate is worth investigating.";
const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

/* ============================== announcement + nav ============================== */

export function Announcement({ onStart }: { onStart: () => void }) {
  const [open, setOpen] = useState(true);
  if (!open) return null;
  return (
    <div className="fo-announce">
      <span className="fo-live">Live</span>
      <span>Agentic drug discovery is live</span>
      <button type="button" className="fo-announce__link" onClick={onStart}>
        Open the workspace <Arrow size={12} />
      </button>
      <button type="button" className="fo-announce__close" onClick={() => setOpen(false)} aria-label="Dismiss announcement">
        <X size={14} />
      </button>
    </div>
  );
}

const NAV = [
  { label: "Sources", id: "sources" },
  { label: "Molecules", id: "paths" },
  { label: "Workflow", id: "workflow" },
  { label: "Pipeline", id: "pipeline" },
  { label: "Activity", id: "activity" },
  { label: "FAQ", id: "faq" },
];

export function Nav({ onStart, theme, onToggleTheme }: { onStart: () => void; theme: "light" | "dark"; onToggleTheme?: () => void }) {
  return (
    <header className="fo-nav">
      <div className="fo-nav-wrap fo-nav__in">
        <div style={{ display: "flex", alignItems: "center" }}>
          <button type="button" className="fo-logo" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} aria-label="bioresearch, back to top">
            <LogoMark size={24} />
            bioresearch
            <span className="fo-beta">beta</span>
          </button>
          <nav className="fo-links" aria-label="Primary">
            <button type="button" onClick={onStart} style={{ color: "var(--fo-ink)", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6 }}>
              Workspace <ChevronDown size={12} />
            </button>
            {NAV.map((n) => (
              <button key={n.id} type="button" onClick={() => scrollTo(n.id)}>
                {n.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="fo-nav__right">
          <button type="button" className="fo-pill" onClick={onStart}>
            New: live search <Arrow size={13} />
          </button>
          <button type="button" className="fo-iconbtn" onClick={onStart} aria-label="Search">
            <Search size={14} />
          </button>
          {onToggleTheme && <ThemeToggle theme={theme} onToggle={onToggleTheme} />}
          <button type="button" className="fo-signin" onClick={onStart}>
            Open workspace
          </button>
        </div>
      </div>
    </header>
  );
}

/* ==================================== hero ==================================== */

const WORDS = ["Mapped.", "Cited.", "Ranked.", "Traced.", "Proven."];
const TARGETS = [
  { name: "EGFR", color: "#2f7cf6" },
  { name: "KRAS", color: "#e4402c" },
  { name: "BACE1", color: "#6e56cf" },
  { name: "CDK4/6", color: "#2ab673" },
  { name: "TP53", color: "#e8822a" },
];

function Hex({ color }: { color: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path d="M16 2.5l11.7 6.75v13.5L16 29.5 4.3 22.75V9.25z" fill={color} />
      <path d="M16 9.5l5.6 3.2v6.6L16 22.5l-5.6-3.2v-6.6z" fill="none" stroke="#fff" strokeWidth="1.8" opacity=".9" />
    </svg>
  );
}

export function Hero({ onStart, onLaunch }: LandingActions) {
  const [i, setI] = useState(0);
  const [out, setOut] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let swap: ReturnType<typeof setTimeout> | undefined;
    const id = setInterval(() => {
      setOut(true);
      swap = setTimeout(() => {
        setI((n) => n + 1);
        setOut(false);
      }, 280);
    }, 2800);
    return () => {
      clearInterval(id);
      if (swap) clearTimeout(swap);
    };
  }, []);

  const target = TARGETS[i % TARGETS.length];

  return (
    <section className="fo-hero" aria-labelledby="hero-title">
      {/* top-left: books */}
      <button type="button" className="fo-float fo-float--stack" onClick={() => onLaunch("Medicinal chemistry and pharmacology of kinase inhibitors")} aria-label="Search medicinal chemistry and pharmacology">
        <span className="fo-book" style={{ left: 0, top: 36, transform: "rotate(-13deg)" }}><BookGreen /></span>
        <span className="fo-book" style={{ left: 86, top: 0, transform: "rotate(9deg)" }}><BookMaroon /></span>
        <span className="fo-book" style={{ left: 40, top: 88, transform: "rotate(-3deg)" }}><BookCream /></span>
      </button>

      {/* top-right: note + checkpoint */}
      <button type="button" className="fo-float fo-float--note fo-card" onClick={() => onLaunch("Allosteric EGFR inhibition in T790M resistant NSCLC")} aria-label="Search allosteric EGFR inhibition">
        <div className="fo-note__kicker">Research note · 021</div>
        <div className="fo-note__title">Allosteric EGFR inhibition</div>
        <div className="fo-note__text">Reversible binders can sidestep the C797S resistance mutation that defeats covalent drugs.</div>
        <div className="fo-note__rule" />
        <div className="fo-note__text">Follow the evidence: which sources support this claim?</div>
        <span className="fo-checkpoint">
          <span className="fo-checkpoint__tag">Sources queried</span>
          <span className="fo-bars" aria-hidden="true"><i /><i /><i /><i /><i /><i /></span>
          <b>6 / 6</b>
        </span>
      </button>

      {/* bottom-left: paper */}
      <button type="button" className="fo-float fo-float--paper fo-card" onClick={() => onLaunch("Structural insights into binding sites in EGFR kinase mutants")} aria-label="Search EGFR kinase binding sites">
        <span className="fo-src-chip" style={{ background: "#b31b1b" }}>arXiv</span>
        <div className="fo-note__title" style={{ fontSize: 14, textAlign: "center", margin: "14px 0 5px", lineHeight: 1.1, fontWeight: 700 }}>
          Structural insights into characterizing binding sites in EGFR kinase mutants
        </div>
        <div className="fo-note__kicker" style={{ textAlign: "center", fontSize: 7.5 }}>arXiv:1812.10602</div>
        <div className="fo-lines" aria-hidden="true">
          {[100, 94, 98, 72, 90].map((w, k) => (
            <i key={k} style={{ width: `${w}%` }} />
          ))}
        </div>
      </button>

      {/* bottom-right: faded */}
      <button type="button" className="fo-float fo-float--faded fo-card" onClick={() => onLaunch("KRAS G12D switch-II pocket inhibitors")} aria-label="Search KRAS G12D inhibitors">
        <div className="fo-note__kicker">Target brief · decision 08</div>
        <div className="fo-note__title" style={{ fontSize: 20 }}>Find the first druggable pocket</div>
        <div className="fo-note__text">Switch-II ligands disrupt effector binding in KRAS G12D. Re-open the decision once binding data is in.</div>
        <div className="fo-note__kicker" style={{ marginTop: 10, color: "#6e56cf" }}>breakpoint</div>
      </button>

      <div className="fo-hero__center">
        <button type="button" className="fo-hero__pill" onClick={onStart}>
          <span className="fo-live">Live</span>
          <span>Six databases, one search</span>
          <span>Try it</span>
          <Arrow size={12} />
        </button>

        <h1 id="hero-title" className="fo-h1">
          <span className="fo-h1__row">
            <span>Everything an</span>
            <span className={`fo-chip ${out ? "is-out" : ""}`} aria-hidden="true">
              <Hex color={target.color} />
              {target.name}
            </span>
          </span>
          <span className="fo-h1__row">
            <span>pro knows.</span>
            <span className={`fo-word ${out ? "is-out" : ""}`}>{WORDS[i % WORDS.length]}</span>
          </span>
        </h1>

        <p className="fo-hero__sub">
          Search PubMed, bioRxiv, arXiv, ChEMBL, PubChem and ClinicalTrials.gov in one place, and get a cited briefing for any target, compound or question.
        </p>

        <div className="fo-hero__cta">
          <button type="button" className="fo-btn" onClick={onStart}>
            Start discovering <Arrow />
          </button>
          <button type="button" className="fo-demo" onClick={() => onLaunch(DEMO_QUERY)}>
            <Play size={14} />
            <span className="fo-link">See demo</span>
          </button>
        </div>
      </div>
    </section>
  );
}

/* ================================ wordmark rows ================================ */

type Mark = { name: string; style?: React.CSSProperties };
const serif: React.CSSProperties = { fontFamily: "var(--font-book), Georgia, serif", fontStyle: "italic", fontWeight: 600 };
const mono: React.CSSProperties = { fontFamily: "var(--font-plex), monospace", fontWeight: 500, letterSpacing: "-0.04em" };
const caps: React.CSSProperties = { fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.04em", fontSize: 16 };
const heavy: React.CSSProperties = { fontWeight: 800, letterSpacing: "-0.05em", fontSize: 21 };
const light: React.CSSProperties = { fontWeight: 400, letterSpacing: "-0.03em" };
const wide: React.CSSProperties = { fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", fontSize: 13 };

const LOGO_ROWS: Mark[][] = [
  [
    { name: "PubMed", style: heavy },
    { name: "bioRxiv", style: serif },
    { name: "arXiv", style: mono },
    { name: "ChEMBL", style: caps },
    { name: "PubChem", style: light },
    { name: "ClinicalTrials.gov", style: wide },
    { name: "NCBI E-utilities", style: serif },
  ],
  [
    { name: "RDKit", style: caps },
    { name: "LangGraph", style: mono },
    { name: "FastAPI", style: heavy },
    { name: "Pydantic", style: serif },
    { name: "Uvicorn", style: wide },
    { name: "Python", style: light },
  ],
  [
    { name: "Next.js", style: heavy },
    { name: "React", style: light },
    { name: "Tailwind CSS", style: mono },
    { name: "TypeScript", style: caps },
    { name: "Lucide", style: serif },
    { name: "Web Speech API", style: wide },
  ],
];

export function SourceMarquee() {
  return (
    <section id="sources" className="fo-logos" aria-label="Data sources and technology">
      <p className="fo-kicker" style={{ marginBottom: 16 }}>Queried live from, and built with</p>
      {LOGO_ROWS.map((row, r) => (
        <div key={r} className={`fo-marquee ${r % 2 ? "fo-marquee--rev" : ""}`} style={{ ["--dur" as string]: `${64 + r * 9}s` }}>
          <div className="fo-marquee__track">
            {[...row, ...row, ...row, ...row].map((m, k) => (
              <span key={k} className="fo-mark" style={m.style} aria-hidden={k >= row.length ? true : undefined}>
                {m.name}
              </span>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

/* ================================== path cards ================================== */

interface PathCard {
  tint: string;
  title: string;
  bullets: string[];
  stat?: string;
  tag?: string;
  query?: string;
  art: React.ReactNode;
}

const PATHS: PathCard[] = [
  { tint: "rgba(219, 162, 146, 0.5)", title: "Literature search", bullets: ["PubMed and bioRxiv abstracts", "arXiv preprints on the same topic", "De-duplicated in one list"], stat: "6 SOURCES · LIVE", query: "EGFR kinase inhibitors", art: <CoverLiterature /> },
  { tint: "rgba(138, 149, 115, 0.5)", title: "Cited briefings", bullets: ["Numbered inline citations", "Hover to preview the source", "Copy the briefing as Markdown"], stat: "INLINE CITATIONS", query: "KRAS G12D allosteric inhibitors", art: <CoverBriefing /> },
  { tint: "rgba(241, 207, 78, 0.5)", title: "Bioactivity data", bullets: ["ChEMBL target records", "IC50 and Ki measurements", "Linked to molecule IDs"], stat: "FROM CHEMBL", query: "CDK4/6 selective inhibitors bioactivity", art: <CoverBioactivity /> },
  { tint: "rgba(127, 162, 195, 0.5)", title: "Compound lookup", bullets: ["Names resolved via PubChem", "Canonical SMILES and properties", "Open the full compound record"], stat: "FROM PUBCHEM", query: "Osimertinib", art: <CoverCompound /> },
  { tint: "rgba(27, 158, 166, 0.5)", title: "Clinical trials", bullets: ["ClinicalTrials.gov records", "Status and summary at a glance", "One click to the registry"], stat: "FROM CLINICALTRIALS.GOV", query: "KRAS G12C inhibitor clinical trials", art: <CoverTrials /> },
  { tint: "rgba(12, 62, 138, 0.5)", title: "Molecule viewer", bullets: ["2D structure diagram", "3D ball-and-stick, drag to rotate", "Atom-level hover details"], tag: "PREVIEW", art: <CoverMolecule /> },
  { tint: "rgba(182, 109, 208, 0.5)", title: "Agent pipeline", bullets: ["Router, researcher and critic", "Self-correcting review loop", "Structured executive dossier"], tag: "SOON", art: <CoverAgents /> },
  { tint: "rgba(34, 34, 33, 0.5)", title: "Property screening", bullets: ["Lipinski rule of five", "Veber and PAINS filters", "Scored candidate shortlist"], tag: "SOON", art: <CoverProperties /> },
];

export function PathGrid({ onLaunch, onStart }: LandingActions) {
  return (
    <section id="paths" className="fo-section" style={{ paddingTop: 72 }}>
      <div className="fo-narrow">
        <div className="fo-kicker">Pick your path</div>
        <h2 className="fo-h2">Choose where to start</h2>
        <div className="fo-paths">
          {PATHS.map((p) => (
            <button key={p.title} type="button" className="fo-path" style={{ ["--tint" as string]: p.tint }} onClick={() => (p.query ? onLaunch(p.query) : onStart())}>
              {p.art}
              {p.tag && <span className="fo-tag">{p.tag}</span>}
              <h3>{p.title}</h3>
              <ul>
                {p.bullets.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
              {p.stat && <span className="fo-stat">{p.stat}</span>}
              <span className="fo-path__open">
                Open <Arrow size={15} />
              </span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ================================== query wall ================================== */

const QUERIES: { q: string; src: string[] }[] = [
  { q: "Novel small molecules for EGFR T790M / C797S resistance", src: ["PubMed", "ChEMBL"] },
  { q: "Allosteric switch-II pocket inhibitors for KRAS G12D", src: ["PubMed", "bioRxiv"] },
  { q: "Dual BACE1 and tau inhibitors with blood-brain barrier permeability", src: ["PubMed", "ChEMBL"] },
  { q: "CDK4/6 inhibitors that overcome palbociclib resistance", src: ["PubMed", "Trials"] },
  { q: "Covalent warheads targeting Cys797", src: ["bioRxiv", "ChEMBL"] },
  { q: "Machine learning in protein design", src: ["arXiv", "bioRxiv"] },
  { q: "Natural product drug discovery with AI", src: ["PubMed", "arXiv"] },
  { q: "Integrating QSAR and deep learning in drug discovery", src: ["arXiv", "PubMed"] },
  { q: "Osimertinib resistance mechanisms in NSCLC", src: ["PubMed", "Trials"] },
  { q: "Clinical trials of KRAS G12C inhibitors", src: ["Trials", "PubMed"] },
];
const SRC_COLOR: Record<string, string> = { PubMed: "#2f7cf6", ChEMBL: "#1b9ea6", bioRxiv: "#c9503a", arXiv: "#b31b1b", Trials: "#2a8a5e" };

export function QueryWall({ onLaunch }: { onLaunch: (q: string) => void }) {
  const rows = [QUERIES.slice(0, 5), QUERIES.slice(5)];
  return (
    <section className="fo-section" aria-label="Example questions" style={{ paddingTop: 72 }}>
      <div className="fo-narrow">
        <div className="fo-kicker">Try a question</div>
        <h2 className="fo-h2" style={{ fontSize: 26.25, lineHeight: "32.8px" }}>Start from a real query</h2>
      </div>
      <div className="fo-wall">
        {rows.map((row, r) => (
          <div key={r} className={`fo-marquee ${r % 2 ? "" : "fo-marquee--rev"}`} style={{ ["--dur" as string]: `${76 + r * 10}s` }}>
            <div className="fo-marquee__track">
              {[...row, ...row, ...row].map((item, k) => (
                <button key={k} type="button" className="fo-q" onClick={() => onLaunch(item.q)} tabIndex={k >= row.length ? -1 : 0} aria-hidden={k >= row.length ? true : undefined}>
                  <span className="fo-q__top">
                    {item.src.map((s) => (
                      <span key={s} className="fo-q__chip" style={{ background: SRC_COLOR[s] }}>{s}</span>
                    ))}
                  </span>
                  <p>{item.q}</p>
                  <span className="fo-q__run">
                    Run this search <Arrow size={13} />
                  </span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ============================== workflow + research box ============================== */

const NOTES = [
  { n: "01", t: "Question", s: "a target or topic", c: "#f7dc4a", pos: { left: "14%", top: "13%" }, rot: -4 },
  { n: "02", t: "Sources", s: "six databases", c: "#e6f25f", pos: { right: "10%", top: "6%" }, rot: 5 },
  { n: "03", t: "Briefing", s: "cited summary", c: "#f4efe2", pos: { left: "32%", top: "34%" }, rot: -6 },
  { n: "04", t: "Citations", s: "hover to preview", c: "#5b95e8", pos: { right: "6%", top: "48%" }, rot: 8 },
  { n: "05", t: "Molecules", s: "2D and 3D viewer", c: "#ef5f6b", pos: { left: "28%", top: "62%" }, rot: -3 },
];

export function Workflow({ onStart, onLaunch }: LandingActions) {
  return (
    <section id="workflow" className="fo-feature">
      <div className="fo-wide fo-split">
        <div className="fo-split__copy">
          <div className="fo-kicker">The workflow</div>
          <h2 className="fo-h2" style={{ fontSize: 30, lineHeight: 1.1, marginTop: 10 }}>One place to go from question to evidence.</h2>
          <p>Drug research usually means a dozen tabs: a literature database, a bioactivity browser, a compound registry and a trial list. Here a single question fans out to all of them at once.</p>
          <p>You get the records side by side, a briefing that points back to each one, and a viewer for the molecules involved. Start broad, then narrow with a follow-up.</p>
          <div className="fo-split__links">
            <button type="button" className="fo-link" onClick={onStart}>Open workspace</button>
            <button type="button" className="fo-link" onClick={() => onLaunch(DEMO_QUERY)}>See an example</button>
          </div>
        </div>

        <div className="fo-box" role="img" aria-label="A research box holding a question, sources, a briefing, citations and molecules">
          <div className="fo-box__sheet" />
          <div className="fo-box__main" />
          <div className="fo-box__flap" />
          <div className="fo-box__foot">Contents<br />of the research box</div>
          {NOTES.map((n) => (
            <div key={n.n} className="fo-sticky" style={n.pos as React.CSSProperties}>
              <span className="fo-sticky__sq" style={{ background: n.c, transform: `rotate(${n.rot}deg)` }} aria-hidden="true" />
              <span>
                <b>{n.n}</b>
                <span>{n.t}</span>
                <small>{n.s}</small>
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ====================================== tiles ====================================== */

const TILES = [
  { bg: "#f2b4ab", n: "01", t: "Search", sub: "Six databases, one box", label: "Free instruments", icon: <IconSearch />, q: "EGFR T790M" },
  { bg: "#e8822a", n: "02", t: "Briefing", sub: "Cited, not just summarised", label: "Evidence", icon: <IconBriefing />, q: "KRAS G12D" },
  { bg: "#fbfbfb", n: "03", t: "Sources", sub: "Inspect every record", label: "Reading order", icon: <IconSources />, q: "BACE1 inhibitors" },
  { bg: "#2b67c6", n: "04", t: "Activity", sub: "See what ran", label: "Transparency", icon: <IconActivity />, q: "CDK4/6", inv: true },
  { bg: "#5cc79a", n: "05", t: "Refine", sub: "Narrow with one click", label: "Follow-ups", icon: <IconRefine />, q: "EGFR resistance mechanisms" },
  { bg: "#c0b6e8", n: "06", t: "Molecules", sub: "2D and 3D viewer", label: "Structure", icon: <IconMolecule />, q: "Osimertinib" },
  { bg: "#68bbe0", n: "07", t: "Listen", sub: "Hear the summary", label: "Audio", icon: <IconListen />, q: "Alzheimer's amyloid" },
  { bg: "#efce7c", n: "08", t: "Export", sub: "Copy as Markdown", label: "Portable", icon: <IconExport />, q: "Natural product drug discovery" },
];

export function Tiles({ onLaunch }: LandingActions) {
  return (
    <section className="fo-section" style={{ paddingTop: 72 }}>
      <div className="fo-wide">
        <div className="fo-kicker">Beyond the search</div>
        <h2 className="fo-h2 fo-h2--lg">
          Everything else in <span className="fo-px" style={{ fontSize: "0.88em" }}>bioresearch</span>.
        </h2>
        <div className="fo-tiles">
          {TILES.map((t) => (
            <button key={t.t} type="button" className={`fo-tile ${t.inv ? "fo-tile--inv" : ""}`} style={{ background: t.bg }} onClick={() => onLaunch(t.q)}>
              <span className="fo-tile__art">{t.icon}</span>
              <span className="fo-tile__num">{t.n}</span>
              <span className="fo-tile__label">{t.label}</span>
              <h3>{t.t}</h3>
              <p>{t.sub}</p>
              <span className="fo-tile__go"><Arrow size={14} /></span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ================================== pipeline ================================== */

export function Pipeline({ onStart, onLaunch }: LandingActions) {
  const steps = [
    { k: "Step 1", big: "Ask", sub: "Any target, compound or question", d: "Type it the way you would say it. Recognised targets such as EGFR or KRAS are echoed back as you type.", cta: "Start a search", act: onStart },
    { k: "Step 2", big: "Retrieve", sub: "Six sources in parallel", d: "PubMed, bioRxiv, arXiv, ChEMBL, PubChem and ClinicalTrials.gov are queried together and de-duplicated.", cta: "See an example", act: () => onLaunch(DEMO_QUERY) },
    { k: "Step 3", big: "Read", sub: "Briefing with citations", d: "Every numbered citation opens the original record, with its abstract, authors, year and link.", cta: "Open the workspace", act: onStart, hi: true },
  ];
  return (
    <section id="pipeline" className="fo-section" style={{ paddingTop: 72 }}>
      <div className="fo-wide">
        <div className="fo-plans-head">
          <div>
            <div className="fo-kicker">How it works</div>
            <h2 className="fo-h2" style={{ fontSize: 26.25, lineHeight: "32.8px" }}>Three steps from question to briefing</h2>
          </div>
          <button type="button" className="fo-btn fo-btn--sm" onClick={onStart}>
            Open workspace <Arrow size={13} />
          </button>
        </div>

        <div className="fo-strip" role="list">
          <div role="listitem">6 live sources</div>
          <div role="listitem">Inline citations</div>
          <div role="listitem">No API keys needed to search</div>
        </div>

        <div className="fo-plans">
          {steps.map((s) => (
            <button key={s.big} type="button" className={`fo-plan ${s.hi ? "fo-plan--hi" : ""}`} onClick={s.act}>
              <div className="fo-plan__top">
                <span className="fo-kicker" style={{ fontSize: 10, fontWeight: 700 }}>{s.k}</span>
                {s.hi && <span className="fo-badge">CITED</span>}
              </div>
              <div className="fo-plan__big">{s.big}</div>
              <div className="fo-plan__sub">{s.sub}</div>
              <p className="fo-plan__desc">{s.d}</p>
              <span className="fo-plan__cta">
                {s.cta} <Arrow size={15} />
              </span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ================================== activity ================================== */

const LOGS = [
  { a: "Router Agent", t: "00:00:01", p: "Decomposed the query into biomedical target entities.", pos: { left: "7%", top: "13%" } },
  { a: "Literature Agent", t: "00:00:07", p: "Ingested records from PubMed, bioRxiv, arXiv, ChEMBL and PubChem.", pos: { right: "6%", top: "35%" } },
  { a: "Synthesizer Agent", t: "00:00:13", p: "Assembled a briefing with inline citations pointing at the retrieved sources.", pos: { left: "13%", top: "64%" } },
];

export function ActivityPanel({ onStart, onLaunch }: LandingActions) {
  return (
    <section id="activity" className="fo-section" style={{ paddingTop: 72 }}>
      <div className="fo-wide fo-activity">
        <div className="fo-panel" role="img" aria-label="Example of the activity log produced by a search">
          <span className="fo-panel__tag">EXAMPLE RUN</span>
          {LOGS.map((l) => (
            <div key={l.a} className="fo-log" style={l.pos as React.CSSProperties}>
              <header>
                <b>{l.a}</b>
                <small>{l.t}</small>
              </header>
              <p>{l.p}</p>
              <span className="fo-ok">Completed</span>
            </div>
          ))}
        </div>

        <div className="fo-activity__copy">
          <div className="fo-kicker">Transparency</div>
          <h2>See exactly what ran.</h2>
          <p>Every search records which steps ran and what each one did. Open the Activity tab in the workspace to follow along, and the Sources tab to read the original records.</p>
          <div className="fo-activity__cta">
            <button type="button" className="fo-btn" onClick={onStart}>
              Open the workspace <Arrow />
            </button>
            <button type="button" className="fo-btn fo-btn--ghost" onClick={() => onLaunch(DEMO_QUERY)}>
              Run an example
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ====================================== FAQ ====================================== */

const FAQ = [
  { q: "Where should I start?", a: "Open the workspace and type a target, compound or question, or click any of the example queries above. A name like EGFR or KRAS G12D works well." },
  { q: "Which sources does it search?", a: "PubMed, bioRxiv, arXiv, ChEMBL, PubChem and ClinicalTrials.gov. They are queried in parallel each time you search, and duplicates are removed." },
  { q: "Do I need API keys?", a: "No. Literature search uses public APIs. You can store provider keys in your browser from the settings button, but the backend does not use them yet." },
  { q: "Is the briefing written by an LLM?", a: "Not yet. The briefing text is a structured template, while the sources, abstracts and links beside it are retrieved live. Always check the cited record. LLM synthesis is the next step." },
  { q: "What if the backend is offline?", a: "The workspace says so. It shows clearly labelled sample content with a retry button, so you never mistake sample data for live results." },
];

export function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section id="faq" className="fo-section" style={{ paddingTop: 72 }}>
      <div className="fo-wide fo-faq">
        <div>
          <div className="fo-kicker">FAQ</div>
          <h2>Questions before you start.</h2>
        </div>
        <div>
          {FAQ.map((f, i) => (
            <div key={f.q} className="fo-acc" data-open={open === i}>
              <button type="button" aria-expanded={open === i} aria-controls={`faq-${i}`} onClick={() => setOpen(open === i ? null : i)}>
                {f.q}
                <ChevronDown size={18} />
              </button>
              <div className="fo-acc__body" id={`faq-${i}`} role="region">
                <div>
                  <p>{f.a}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ================================ CTA + footer ================================ */

export function CtaCard({ onStart }: { onStart: () => void }) {
  return (
    <section className="fo-narrow" style={{ paddingTop: 56 }}>
      <div className="fo-cta">
        <div>
          <div className="fo-kicker">Three steps / one briefing</div>
          <h2>Run your first search.</h2>
          <p>Ask a question, read the sources, follow the citations.</p>
        </div>
        <button type="button" className="fo-btn" onClick={onStart}>
          Get started <Arrow />
        </button>
      </div>
    </section>
  );
}

export function Footer({ onStart, onLaunch, onOpenKeys }: LandingActions) {
  return (
    <footer className="fo-foot">
      <div className="fo-nav-wrap">
        <div className="fo-foot__grid">
          <div>
            <span className="fo-logo" style={{ cursor: "default" }}>
              <LogoMark size={22} />
              bioresearch
            </span>
            <p>Search the biomedical literature, bioactivity data and clinical trials together, and read the evidence behind every claim.</p>
          </div>
          <div>
            <h4>Workspace</h4>
            <ul>
              <li><button type="button" onClick={onStart}>Search</button></li>
              <li><button type="button" onClick={() => onLaunch("Osimertinib")}>Compounds</button></li>
              <li><button type="button" onClick={() => onLaunch(DEMO_QUERY)}>Example briefing</button></li>
              <li><button type="button" onClick={onOpenKeys}>AI provider keys</button></li>
            </ul>
          </div>
          <div>
            <h4>Data sources</h4>
            <ul>
              <li><a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank" rel="noopener noreferrer">PubMed</a></li>
              <li><a href="https://www.biorxiv.org/" target="_blank" rel="noopener noreferrer">bioRxiv</a></li>
              <li><a href="https://arxiv.org/" target="_blank" rel="noopener noreferrer">arXiv</a></li>
              <li><a href="https://www.ebi.ac.uk/chembl/" target="_blank" rel="noopener noreferrer">ChEMBL</a></li>
              <li><a href="https://pubchem.ncbi.nlm.nih.gov/" target="_blank" rel="noopener noreferrer">PubChem</a></li>
              <li><a href="https://clinicaltrials.gov/" target="_blank" rel="noopener noreferrer">ClinicalTrials.gov</a></li>
            </ul>
          </div>
          <div>
            <h4>Built with</h4>
            <ul>
              <li><a href="https://nextjs.org/" target="_blank" rel="noopener noreferrer">Next.js</a></li>
              <li><a href="https://fastapi.tiangolo.com/" target="_blank" rel="noopener noreferrer">FastAPI</a></li>
              <li><a href="https://www.rdkit.org/" target="_blank" rel="noopener noreferrer">RDKit</a></li>
              <li><a href="https://www.langchain.com/langgraph" target="_blank" rel="noopener noreferrer">LangGraph</a></li>
            </ul>
          </div>
        </div>
        <div className="fo-foot__bar">
          <span>© 2026 BioResearch AI</span>
          <span>Results come from public databases. Verify against the original records.</span>
        </div>
      </div>
    </footer>
  );
}
