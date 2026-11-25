"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Star,
  Settings,
  ArrowLeft,
  Send,
  X,
  ExternalLink,
  Copy,
  Check,
  BookOpen,
  RefreshCw,
  Volume2,
  VolumeX,
  Loader2,
  Sparkles,
  CheckCircle2,
  TriangleAlert,
  PanelRight,
  SearchX,
  Info,
} from "lucide-react";
import GroundedTextRenderer from "./GroundedTextRenderer";
import ChemicalStructureViewer from "./ChemicalStructureViewer";
import ThemeToggle from "./ThemeToggle";
import {
  formatAuthors,
  sourceBadgeClass,
  type CitationItem,
  type ResearchResponse,
} from "@/lib/research";

interface DrugDiscoveryWorkspaceProps {
  initialQuery: string;
  theme?: "light" | "dark";
  onToggleTheme?: () => void;
  onBackToSearch: () => void;
  onOpenApiKeys: () => void;
}

type Status = "loading" | "success" | "error";
type RightTab = "Sources" | "Ask" | "Activity" | "Chemical";

const RIGHT_TABS: { id: RightTab; label: string }[] = [
  { id: "Sources", label: "Sources" },
  { id: "Ask", label: "Refine" },
  { id: "Activity", label: "Activity" },
  { id: "Chemical", label: "Chemistry" },
];

const REFINEMENTS = [
  "resistance mechanisms",
  "known inhibitors and IC50 values",
  "clinical trials",
  "off-target and safety signals",
];

const SOURCE_NAMES = ["PubMed", "bioRxiv", "arXiv", "ChEMBL", "PubChem", "ClinicalTrials.gov"];

export default function DrugDiscoveryWorkspace({
  initialQuery,
  theme = "dark",
  onToggleTheme,
  onBackToSearch,
  onOpenApiKeys,
}: DrugDiscoveryWorkspaceProps) {
  const isDark = theme === "dark";
  const pick = (dark: string, light: string) => (isDark ? dark : light);

  // --- UI state ---------------------------------------------------------
  const [followUpInput, setFollowUpInput] = useState("");
  const [activeRightTab, setActiveRightTab] = useState<RightTab>("Sources");
  const [selectedSource, setSelectedSource] = useState<CitationItem | null>(null);
  const [isCopied, setIsCopied] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [starred, setStarred] = useState(false);
  // This component only mounts after a click (never server-rendered), so reading window here is safe.
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(() => window.innerWidth >= 1024);

  // --- Research request state ------------------------------------------
  const [queryText, setQueryText] = useState(initialQuery);
  const [reloadNonce, setReloadNonce] = useState(0);
  const [status, setStatus] = useState<Status>("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [data, setData] = useState<ResearchResponse | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const followUpRef = useRef<HTMLInputElement>(null);

  const sections = data?.notebook_data?.sections ?? [];
  const citations = useMemo<CitationItem[]>(
    () => data?.notebook_data?.citations ?? data?.ranked_documents ?? [],
    [data]
  );
  const reasoningLogs = data?.reasoning_logs ?? [];
  const isDemo = data?.data_source === "demo";
  const isLoading = status === "loading";

  const sourceCounts = useMemo(() => {
    const counts = new Map<string, number>();
    citations.forEach((c) => counts.set(c.source, (counts.get(c.source) ?? 0) + 1));
    return [...counts.entries()];
  }, [citations]);

  // Start (or restart) a search. State changes live in the handler; the effect below only does the async work.
  const runSearch = (query: string) => {
    window.speechSynthesis?.cancel();
    setIsPlayingAudio(false);
    setQueryText(query);
    setStatus("loading");
    setErrorMessage("");
    setElapsed(0);
    setReloadNonce((n) => n + 1);
  };

  // Fetch the dossier. Cleanup aborts the in-flight request, so a slow earlier answer can never overwrite a newer one.
  useEffect(() => {
    const controller = new AbortController();

    fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: queryText.trim() }),
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.error || `The research service returned HTTP ${res.status}.`);
        }
        return (await res.json()) as ResearchResponse;
      })
      .then((payload) => {
        const list = payload.notebook_data?.citations ?? payload.ranked_documents ?? [];
        setData(payload);
        setSelectedSource(list[0] ?? null);
        setElapsed(payload.execution_time_seconds ?? 0);
        setStatus("success");
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setErrorMessage(err instanceof Error ? err.message : "Something went wrong while contacting the research service.");
        setStatus("error");
      });

    return () => controller.abort();
  }, [queryText, reloadNonce]);

  // Live stopwatch while loading
  useEffect(() => {
    if (status !== "loading") return;
    const t0 = Date.now();
    const id = setInterval(() => setElapsed((Date.now() - t0) / 1000), 200);
    return () => clearInterval(id);
  }, [status, reloadNonce]);

  // Stop any speech if the workspace unmounts
  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  // --- Handlers ---------------------------------------------------------
  const handleFollowUpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const next = followUpInput.trim();
    if (!next || isLoading) return;
    setFollowUpInput("");
    runSearch(next);
  };

  const openSource = (cite: CitationItem) => {
    setSelectedSource(cite);
    setActiveRightTab("Sources");
    setIsRightPanelOpen(true);
  };

  const toggleAudioBriefing = () => {
    if (!("speechSynthesis" in window)) return;
    if (isPlayingAudio) {
      window.speechSynthesis.cancel();
      setIsPlayingAudio(false);
      return;
    }
    if (!sections.length) return;
    const text = `Briefing on ${queryText}. ${sections[0].title}. ${sections[0].content
      .replace(/\[\d+\]/g, "")
      .replace(/\*\*/g, "")}`;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.05;
    utterance.onend = () => setIsPlayingAudio(false);
    utterance.onerror = () => setIsPlayingAudio(false);
    window.speechSynthesis.speak(utterance);
    setIsPlayingAudio(true);
  };

  const handleCopyDossier = async () => {
    const body = sections.map((s) => `## ${s.title}\n${s.content}\n`).join("\n");
    const refs = citations
      .map((c) => `[${c.citation_index}] ${c.title} (${c.source}, ${c.year})${c.url ? ` ${c.url}` : ""}`)
      .join("\n");
    const markdown = `# Research Briefing: ${queryText}\n\n${body}\n## Sources\n${refs}\n`;
    try {
      await navigator.clipboard.writeText(markdown);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 1800);
    } catch {
      /* clipboard unavailable (insecure context / permission denied) */
    }
  };

  // --- Shared style fragments ------------------------------------------
  const iconButton = `p-2 rounded-lg border transition-colors ${pick(
    "border-white/10 text-slate-400 hover:text-white hover:bg-white/5",
    "border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-100"
  )}`;
  const card = pick("bg-[#18191E]/70 border-white/5", "bg-white border-slate-200/90 shadow-sm shadow-slate-200/50");
  const mutedText = pick("text-slate-400", "text-slate-500");

  return (
    <div
      className={`flex flex-col h-dvh overflow-hidden font-sans transition-colors duration-200 ${pick(
        "bg-[#121316] text-slate-100",
        "bg-[#FAFAFC] text-slate-900"
      )}`}
    >
      {/* ============================ HEADER ============================ */}
      <header
        className={`h-14 px-3 sm:px-6 flex items-center justify-between gap-3 shrink-0 select-none ${pick(
          "bg-[#18191E] border-b border-white/5",
          "bg-white border-b border-slate-200"
        )}`}
      >
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <button
            type="button"
            onClick={onBackToSearch}
            className={`p-1.5 rounded-lg transition-colors ${pick(
              "text-slate-400 hover:text-white hover:bg-white/5",
              "text-slate-500 hover:text-slate-900 hover:bg-slate-100"
            )}`}
            aria-label="Back to search"
            title="Back to search"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-2 min-w-0">
            <div className="w-6 h-6 rounded-md bg-blue-600 flex items-center justify-center text-white shrink-0">
              <BookOpen className="w-3.5 h-3.5" aria-hidden="true" />
            </div>
            <span className="font-bold text-sm tracking-tight truncate">BioResearch AI</span>
            <span className={`hidden sm:inline ${mutedText}`}>/</span>
            <span className={`hidden sm:inline text-sm truncate ${pick("text-slate-300", "text-slate-600")}`}>
              Research briefing
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
          {onToggleTheme && <ThemeToggle theme={theme} onToggle={onToggleTheme} />}

          <button
            type="button"
            onClick={() => runSearch(queryText)}
            disabled={isLoading}
            className={`${iconButton} disabled:opacity-60`}
            aria-label="Re-run search"
            title="Re-run search"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-500" : ""}`} />
          </button>

          <button
            type="button"
            onClick={toggleAudioBriefing}
            disabled={!sections.length}
            aria-pressed={isPlayingAudio}
            className={`px-2.5 sm:px-3 py-2 sm:py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 border transition-all disabled:opacity-50 ${
              isPlayingAudio
                ? "bg-purple-600/20 border-purple-500/50 text-purple-500"
                : pick(
                    "bg-white/5 border-white/10 text-slate-300 hover:text-white hover:bg-white/10",
                    "bg-slate-100 border-slate-200 text-slate-700 hover:bg-slate-200"
                  )
            }`}
            title="Read the executive summary aloud"
          >
            {isPlayingAudio ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5 text-purple-500" />}
            <span className="hidden md:inline">{isPlayingAudio ? "Stop" : "Listen"}</span>
          </button>

          <button
            type="button"
            onClick={handleCopyDossier}
            disabled={!sections.length}
            className={`${iconButton} disabled:opacity-50`}
            aria-label="Copy briefing as Markdown"
            title="Copy briefing as Markdown"
          >
            {isCopied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
          </button>

          <button
            type="button"
            onClick={() => setStarred((v) => !v)}
            aria-pressed={starred}
            className={`hidden sm:block p-2 rounded-lg border transition-colors ${
              starred ? "bg-amber-500/20 border-amber-500/40 text-amber-500" : iconButton
            }`}
            aria-label="Bookmark this briefing"
            title="Bookmark (this session only)"
          >
            <Star className={`w-4 h-4 ${starred ? "fill-amber-500" : ""}`} />
          </button>

          <button type="button" onClick={onOpenApiKeys} className={`hidden sm:block ${iconButton}`} aria-label="AI provider keys" title="AI provider keys">
            <Settings className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={() => setIsRightPanelOpen((v) => !v)}
            aria-pressed={isRightPanelOpen}
            className={`${iconButton} ${isRightPanelOpen ? pick("bg-white/10 text-white", "bg-slate-100 text-slate-900") : ""}`}
            aria-label={isRightPanelOpen ? "Hide sources panel" : "Show sources panel"}
            title={isRightPanelOpen ? "Hide sources panel" : "Show sources panel"}
          >
            <PanelRight className="w-4 h-4" />
          </button>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden relative">
        {/* ============================ MAIN FEED ============================ */}
        <main className="flex-1 min-w-0 overflow-y-auto" aria-busy={isLoading}>
          <div className="max-w-3xl w-full mx-auto px-4 sm:px-10 pt-8 space-y-6">
            {/* Title block */}
            <div className={`border-b pb-5 space-y-3 ${pick("border-white/10", "border-slate-200")}`}>
              <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  {isLoading ? (
                    <span className={`px-2.5 py-1 rounded-full font-mono text-[11px] font-semibold flex items-center gap-1.5 border ${pick("bg-white/5 border-white/10 text-slate-300", "bg-slate-100 border-slate-200 text-slate-600")}`}>
                      <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />
                      Searching&hellip;
                    </span>
                  ) : status === "error" ? (
                    <span className="px-2.5 py-1 rounded-full font-mono text-[11px] font-semibold border bg-red-500/10 border-red-500/30 text-red-500">
                      Request failed
                    </span>
                  ) : (
                    <span
                      className={`px-2.5 py-1 rounded-full font-mono text-[11px] font-semibold flex items-center gap-1.5 border ${
                        isDemo
                          ? "bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-400"
                          : pick("bg-emerald-500/10 border-emerald-500/30 text-emerald-300", "bg-emerald-50 border-emerald-200 text-emerald-700")
                      }`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${isDemo ? "bg-amber-500" : "bg-emerald-500"}`} />
                      {isDemo ? "Sample data" : `${citations.length} live ${citations.length === 1 ? "source" : "sources"}`}
                    </span>
                  )}
                </div>

                <span className={`text-[11px] font-mono tabular-nums ${mutedText}`} aria-live="polite">
                  {isLoading ? `${elapsed.toFixed(1)}s` : status === "success" && !isDemo ? `Completed in ${elapsed.toFixed(1)}s` : ""}
                </span>
              </div>

              <h1 className={`text-2xl sm:text-3xl font-extrabold tracking-tight leading-tight text-balance ${pick("text-white", "text-slate-900")}`}>
                {queryText}
              </h1>

              {!isLoading && sourceCounts.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5">
                  {sourceCounts.map(([name, count]) => (
                    <span key={name} className={`px-2 py-0.5 rounded-md border text-[10px] font-mono font-semibold ${sourceBadgeClass(name, isDark)}`}>
                      {name} · {count}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Demo-data banner */}
            {status === "success" && isDemo && (
              <div role="status" className={`rounded-xl border p-4 flex items-start gap-3 text-sm animate-fadeIn ${pick("bg-amber-500/10 border-amber-500/30 text-amber-100", "bg-amber-50 border-amber-200 text-amber-900")}`}>
                <TriangleAlert className="w-4 h-4 mt-0.5 shrink-0 text-amber-500" aria-hidden="true" />
                <div className="flex-1 space-y-1">
                  <p className="font-semibold">You&apos;re looking at sample content, not live results.</p>
                  <p className="text-xs leading-relaxed opacity-90">
                    {(data?.fallback_reason || "The research backend is unavailable").replace(/\.$/, "")}. Start it with{" "}
                    <code className="font-mono px-1 py-0.5 rounded bg-black/10 dark:bg-white/10">uvicorn api.server:app --port 8000</code>{" "}
                    and retry.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => runSearch(queryText)}
                  className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-500 text-slate-950 hover:bg-amber-400 transition-colors"
                >
                  Retry
                </button>
              </div>
            )}

            {/* Error banner */}
            {status === "error" && (
              <div role="alert" className={`rounded-xl border p-4 flex items-start gap-3 text-sm animate-fadeIn ${pick("bg-red-500/10 border-red-500/30 text-red-100", "bg-red-50 border-red-200 text-red-900")}`}>
                <TriangleAlert className="w-4 h-4 mt-0.5 shrink-0 text-red-500" aria-hidden="true" />
                <div className="flex-1 space-y-1">
                  <p className="font-semibold">We couldn&apos;t complete that search.</p>
                  <p className="text-xs leading-relaxed opacity-90">{errorMessage}</p>
                </div>
                <button
                  type="button"
                  onClick={() => runSearch(queryText)}
                  className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold bg-red-500 text-white hover:bg-red-400 transition-colors"
                >
                  Try again
                </button>
              </div>
            )}

            {/* Loading: honest indeterminate progress + skeleton cards */}
            {isLoading && (
              <div className="space-y-5 animate-fadeIn">
                <div className={`rounded-xl p-4 space-y-3 border ${pick("bg-[#18191E] border-white/10", "bg-white border-slate-200 shadow-sm")}`}>
                  <div className="flex items-center justify-between gap-3 text-xs">
                    <span className="font-semibold flex items-center gap-2">
                      <Loader2 className="w-3.5 h-3.5 text-blue-500 animate-spin" aria-hidden="true" />
                      Querying {SOURCE_NAMES.length} sources in parallel
                    </span>
                    <span className={`font-mono tabular-nums ${mutedText}`}>{elapsed.toFixed(1)}s</span>
                  </div>
                  <div className={`w-full h-1.5 rounded-full overflow-hidden ${pick("bg-slate-800", "bg-slate-100")}`} role="progressbar" aria-label="Searching literature databases">
                    <div className="h-full rounded-full bg-gradient-to-r from-blue-600 to-cyan-500 progress-indeterminate" />
                  </div>
                  <p className={`text-[11px] ${mutedText}`}>
                    {SOURCE_NAMES.join(" · ")}. Some databases take 10–30 seconds to respond.
                  </p>
                </div>

                {[0, 1, 2].map((i) => (
                  <div key={i} className={`rounded-2xl p-6 border space-y-3 ${card}`} aria-hidden="true">
                    <div className="skeleton h-5 w-1/3 rounded-md" />
                    <div className="skeleton h-3.5 w-full rounded" />
                    <div className="skeleton h-3.5 w-[92%] rounded" />
                    <div className="skeleton h-3.5 w-[70%] rounded" />
                  </div>
                ))}
              </div>
            )}

            {/* Briefing sections */}
            {!isLoading && status === "success" && (
              <div className="space-y-5 animate-fadeIn">
                {sections.length === 0 && (
                  <div className={`rounded-2xl p-10 border text-center space-y-2 ${card}`}>
                    <SearchX className={`w-8 h-8 mx-auto ${mutedText}`} aria-hidden="true" />
                    <p className="font-semibold">No results for this query</p>
                    <p className={`text-sm ${mutedText}`}>Try a more specific target, gene or compound name.</p>
                  </div>
                )}

                {sections.map((section) => (
                  <section key={section.id} className={`rounded-2xl p-5 sm:p-7 border space-y-3 transition-colors ${card} ${pick("hover:border-white/10", "hover:border-slate-300")}`}>
                    <h2 className={`text-base sm:text-lg font-bold tracking-tight flex items-center gap-2 pb-2 border-b ${pick("text-white border-white/5", "text-slate-900 border-slate-100")}`}>
                      <span className="w-1.5 h-4 rounded-full bg-blue-600" aria-hidden="true" />
                      {section.title}
                    </h2>
                    <GroundedTextRenderer content={section.content} citations={citations} theme={theme} onSelectSource={openSource} />
                  </section>
                ))}

                {sections.length > 0 && (
                  <p className={`flex items-start gap-2 text-xs leading-relaxed ${mutedText}`}>
                    <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" aria-hidden="true" />
                    Hover or focus a numbered citation to preview the source excerpt; click it to open the full record.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Sticky follow-up bar */}
          <div className={`sticky bottom-0 mt-6 pt-6 pb-4 px-4 sm:px-10 bg-gradient-to-t ${pick("from-[#121316] via-[#121316]/95", "from-[#FAFAFC] via-[#FAFAFC]/95")} to-transparent`}>
            <form
              onSubmit={handleFollowUpSubmit}
              className={`max-w-3xl mx-auto rounded-2xl p-1.5 border shadow-lg flex items-center gap-2 transition-all ${pick(
                "bg-[#18191E] border-white/10 focus-within:border-blue-500/60",
                "bg-white border-slate-200 focus-within:border-blue-500 shadow-slate-200/60"
              )}`}
            >
              <label htmlFor="follow-up" className="sr-only">
                Search a new or refined query
              </label>
              <input
                id="follow-up"
                ref={followUpRef}
                type="text"
                value={followUpInput}
                onChange={(e) => setFollowUpInput(e.target.value)}
                placeholder="Refine or start a new search, e.g. “EGFR resistance mutations”"
                className={`flex-1 min-w-0 bg-transparent px-3 py-2 text-sm outline-none ${pick("text-white placeholder:text-slate-500", "text-slate-900 placeholder:text-slate-400")}`}
              />
              <button
                type="submit"
                disabled={isLoading || !followUpInput.trim()}
                className="w-9 h-9 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:hover:bg-blue-600 text-white flex items-center justify-center transition-all shrink-0"
                aria-label="Run search"
                title="Run search"
              >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </form>
          </div>
        </main>

        {/* ============================ SIDE PANEL ============================ */}
        {isRightPanelOpen && (
          <>
            {/* Backdrop for the mobile drawer */}
            <button
              type="button"
              aria-label="Close sources panel"
              onClick={() => setIsRightPanelOpen(false)}
              className="lg:hidden fixed inset-0 z-30 bg-black/50 cursor-default"
              tabIndex={-1}
            />

            <aside
              className={`fixed lg:static inset-y-0 right-0 z-40 w-[min(24rem,92vw)] lg:w-96 border-l flex flex-col shrink-0 shadow-2xl lg:shadow-none animate-fadeIn ${pick(
                "bg-[#18191E] border-white/5",
                "bg-white border-slate-200"
              )}`}
              aria-label="Sources and tools"
            >
              <div className={`p-4 border-b flex items-center justify-between shrink-0 ${pick("border-white/5", "border-slate-100")}`}>
                <div>
                  <h2 className="font-bold text-sm flex items-center gap-1.5">
                    <BookOpen className="w-4 h-4 text-blue-500" aria-hidden="true" />
                    Sources
                  </h2>
                  <span className={`text-[11px] font-mono ${mutedText}`}>
                    {isLoading ? "Loading…" : `${citations.length} ${citations.length === 1 ? "reference" : "references"}`}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setIsRightPanelOpen(false)}
                  className={`p-1.5 rounded-lg transition-colors ${pick("text-slate-400 hover:text-white hover:bg-white/5", "text-slate-400 hover:text-slate-900 hover:bg-slate-100")}`}
                  aria-label="Close panel"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Tabs */}
              <div role="tablist" aria-label="Panel sections" className={`flex items-center px-3 pt-2 border-b text-xs font-semibold shrink-0 ${pick("border-white/5", "border-slate-100")}`}>
                {RIGHT_TABS.map((tab) => {
                  const active = activeRightTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      role="tab"
                      aria-selected={active}
                      onClick={() => setActiveRightTab(tab.id)}
                      className={`pb-2 px-2.5 transition-colors relative ${
                        active ? pick("text-white", "text-slate-900") : pick("text-slate-400 hover:text-slate-200", "text-slate-500 hover:text-slate-800")
                      }`}
                    >
                      {tab.label}
                      {active && <span className="absolute bottom-0 left-1 right-1 h-0.5 bg-blue-600 rounded-full" />}
                    </button>
                  );
                })}
              </div>

              <div className="flex-1 overflow-y-auto" role="tabpanel">
                {/* SOURCES */}
                {activeRightTab === "Sources" && (
                  <div className="p-4 space-y-4">
                    {isLoading && (
                      <div className="space-y-2" aria-hidden="true">
                        {[0, 1, 2, 3].map((i) => (
                          <div key={i} className="skeleton h-16 rounded-lg" />
                        ))}
                      </div>
                    )}

                    {!isLoading && selectedSource && (
                      <div className={`rounded-xl p-4 space-y-3 border animate-fadeIn ${pick("bg-[#121316] border-blue-500/30", "bg-slate-50 border-blue-200")}`}>
                        <div className="flex items-center justify-between gap-2">
                          <span className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] border ${sourceBadgeClass(selectedSource.source, isDark)}`}>
                            [{selectedSource.citation_index}] {selectedSource.source}
                          </span>
                          <span className="font-mono text-slate-400 text-[10px]">{selectedSource.year}</span>
                        </div>

                        <h3 className="text-sm font-bold leading-snug">{selectedSource.title}</h3>
                        <p className={`text-[11px] ${pick("text-slate-400", "text-slate-600")}`}>{formatAuthors(selectedSource.authors)}</p>

                        {selectedSource.evidence_quote && (
                          <blockquote className={`p-2.5 rounded-lg border ${pick("bg-black/40 border-white/5", "bg-white border-slate-200")}`}>
                            <span className={`text-[9px] font-mono uppercase tracking-wider block mb-0.5 ${pick("text-cyan-400", "text-blue-600 font-bold")}`}>
                              Excerpt
                            </span>
                            <p className={`text-xs italic leading-relaxed ${pick("text-slate-200", "text-slate-800")}`}>
                              &ldquo;{selectedSource.evidence_quote}&rdquo;
                            </p>
                          </blockquote>
                        )}

                        <div className="space-y-1">
                          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 block">Abstract</span>
                          <p className={`text-xs leading-relaxed max-h-48 overflow-y-auto pr-1 whitespace-pre-line ${pick("text-slate-300", "text-slate-700")}`}>
                            {selectedSource.abstract || "No abstract available for this record."}
                          </p>
                        </div>

                        {selectedSource.url && (
                          <a
                            href={selectedSource.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={`w-full py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors border ${pick(
                              "bg-white/5 hover:bg-white/10 text-blue-400 border-white/10",
                              "bg-white hover:bg-slate-100 text-blue-700 border-slate-200"
                            )}`}
                          >
                            Open in {selectedSource.source}
                            <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                          </a>
                        )}
                      </div>
                    )}

                    {!isLoading && !selectedSource && (
                      <p className="text-xs text-slate-500 text-center py-6">
                        {status === "error" ? "No sources were loaded." : "Select a citation to inspect the source here."}
                      </p>
                    )}

                    {!isLoading && citations.length > 0 && (
                      <div className={`pt-3 border-t space-y-2 ${pick("border-white/5", "border-slate-100")}`}>
                        <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">
                          All sources ({citations.length})
                        </span>
                        <ul className="space-y-2">
                          {citations.map((cite) => {
                            const active = selectedSource?.citation_index === cite.citation_index;
                            return (
                              <li key={`${cite.citation_index}-${cite.id}`}>
                                <button
                                  type="button"
                                  onClick={() => setSelectedSource(cite)}
                                  aria-current={active}
                                  className={`w-full text-left p-2.5 rounded-lg border transition-all text-xs ${
                                    active
                                      ? pick("bg-blue-600/10 border-blue-500/40", "bg-blue-50/80 border-blue-300")
                                      : pick("bg-[#121316] border-white/5 hover:border-white/15", "bg-slate-50 border-slate-200/70 hover:bg-slate-100")
                                  }`}
                                >
                                  <div className="flex items-center justify-between text-[10px] font-mono mb-1">
                                    <span className={`px-1.5 py-px rounded border font-bold ${sourceBadgeClass(cite.source, isDark)}`}>
                                      [{cite.citation_index}] {cite.source}
                                    </span>
                                    <span className="text-slate-400">{cite.year}</span>
                                  </div>
                                  <span className="font-semibold leading-snug line-clamp-2 block">{cite.title}</span>
                                </button>
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* REFINE */}
                {activeRightTab === "Ask" && (
                  <div className="p-4 space-y-3 text-xs">
                    <p className={pick("text-slate-400", "text-slate-600")}>
                      Narrow this search. Each option runs a new search for &ldquo;{queryText}&rdquo; plus that angle.
                    </p>
                    <div className="space-y-2">
                      {REFINEMENTS.map((angle) => (
                        <button
                          key={angle}
                          type="button"
                          disabled={isLoading}
                          onClick={() => runSearch(`${queryText} ${angle}`)}
                          className={`w-full text-left px-3 py-2.5 rounded-xl border transition-colors disabled:opacity-50 ${pick(
                            "bg-[#121316] border-white/5 text-slate-300 hover:border-blue-500/40",
                            "bg-slate-50 border-slate-200 text-slate-700 hover:border-blue-400"
                          )}`}
                        >
                          + {angle}
                        </button>
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={() => followUpRef.current?.focus()}
                      className="text-blue-500 hover:text-blue-400 font-semibold"
                    >
                      Or type your own query ↓
                    </button>
                  </div>
                )}

                {/* ACTIVITY */}
                {activeRightTab === "Activity" && (
                  <div className="p-4 space-y-3 text-xs font-mono">
                    <div className={mutedText}>What the pipeline did for this search</div>
                    {isLoading && <div className="skeleton h-14 rounded-lg" aria-hidden="true" />}
                    {!isLoading && reasoningLogs.length === 0 && <p className="text-slate-500">No activity recorded.</p>}
                    {reasoningLogs.map((log, i) => (
                      <div key={i} className={`p-2.5 rounded-lg border space-y-1 ${pick("bg-[#121316] border-white/5", "bg-slate-50 border-slate-200")}`}>
                        <div className="flex items-center justify-between text-[10px] text-slate-400">
                          <span className={`font-semibold ${pick("text-cyan-400", "text-blue-600")}`}>{log.agent}</span>
                          <span>{log.timestamp}</span>
                        </div>
                        <p className={`text-[11px] leading-relaxed ${pick("text-slate-300", "text-slate-700")}`}>{log.thought}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* CHEMISTRY */}
                {activeRightTab === "Chemical" && (
                  <div className="p-4 space-y-4">
                    <p className={`text-xs flex items-start gap-1.5 ${pick("text-slate-400", "text-slate-600")}`}>
                      <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" aria-hidden="true" />
                      Illustrative example structure. It is not generated from this search.
                    </p>
                    <ChemicalStructureViewer moleculeName="Candidate A-17" theme={theme} />
                  </div>
                )}
              </div>

              {/* Connection status */}
              <div className={`p-3 border-t text-[11px] font-mono flex items-center justify-between shrink-0 ${pick("border-white/5 text-slate-500", "border-slate-100 text-slate-500 bg-slate-50")}`}>
                {isLoading ? (
                  <span className="flex items-center gap-1.5">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" /> Contacting backend…
                  </span>
                ) : status === "error" ? (
                  <span className="flex items-center gap-1.5 text-red-500 font-medium">
                    <TriangleAlert className="w-3.5 h-3.5" aria-hidden="true" /> Request failed
                  </span>
                ) : isDemo ? (
                  <span className="flex items-center gap-1.5 text-amber-500 font-medium">
                    <TriangleAlert className="w-3.5 h-3.5" aria-hidden="true" /> Backend offline · sample data
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" /> Live backend
                  </span>
                )}
                <span className="flex items-center gap-1">
                  <Sparkles className="w-3 h-3" aria-hidden="true" /> {citations.length} sources
                </span>
              </div>
            </aside>
          </>
        )}
      </div>
    </div>
  );
}
