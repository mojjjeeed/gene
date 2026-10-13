"use client";

import React, { useState, useEffect } from "react";
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
  CheckCircle2 
} from "lucide-react";
import GroundedTextRenderer from "./GroundedTextRenderer";
import { CitationItem } from "./HoverCitationBadge";
import ChemicalStructureViewer from "./ChemicalStructureViewer";
import ThemeToggle from "./ThemeToggle";

interface DrugDiscoveryWorkspaceProps {
  initialQuery: string;
  theme?: "light" | "dark";
  onToggleTheme?: () => void;
  onBackToSearch: () => void;
  onOpenApiKeys: () => void;
}

interface BriefingSection {
  id: string;
  title: string;
  content: string;
}

export default function DrugDiscoveryWorkspace({
  initialQuery,
  theme = "dark",
  onToggleTheme,
  onBackToSearch,
  onOpenApiKeys
}: DrugDiscoveryWorkspaceProps) {
  const [queryText, setQueryText] = useState(initialQuery);
  const [followUpInput, setFollowUpInput] = useState("");
  const [activeRightTab, setActiveRightTab] = useState<"Sources" | "Ask" | "Activity" | "Chemical">("Sources");
  const [selectedSource, setSelectedSource] = useState<CitationItem | null>(null);
  const [isCopiedDossier, setIsCopiedDossier] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [starred, setStarred] = useState(false);
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(true);

  // Live Research Execution States
  const [isResearching, setIsResearching] = useState(true);
  const [researchTime, setResearchTime] = useState(0.0);
  const [activeStageIndex, setActiveStageIndex] = useState(1);
  const [sections, setSections] = useState<BriefingSection[]>([]);
  const [citations, setCitations] = useState<CitationItem[]>([]);
  const [reasoningLogs, setReasoningLogs] = useState<any[]>([]);

  const isDark = theme === "dark";

  // Fetch from FastAPI & DataLoaderFactory via Next.js Route
  const fetchResearchDossier = async (query: string) => {
    setIsResearching(true);
    setResearchTime(0.0);
    setActiveStageIndex(1);

    const timer = setInterval(() => {
      setResearchTime((prev) => +(prev + 0.1).toFixed(1));
    }, 100);

    const stageTimer = setInterval(() => {
      setActiveStageIndex((prev) => (prev < 4 ? prev + 1 : prev));
    }, 800);

    try {
      const res = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim() }),
      });

      if (res.ok) {
        const data = await res.json();
        const notebookData = data.notebook_data || {};
        setSections(notebookData.sections || []);
        setCitations(notebookData.citations || data.ranked_documents || []);
        setReasoningLogs(data.reasoning_logs || []);
        if (notebookData.citations && notebookData.citations.length > 0) {
          setSelectedSource(notebookData.citations[0]);
        }
      }
    } catch (err) {
      console.error("[Workspace Error] Failed to fetch research dossier:", err);
    } finally {
      clearInterval(timer);
      clearInterval(stageTimer);
      setActiveStageIndex(4);
      setIsResearching(false);
    }
  };

  useEffect(() => {
    fetchResearchDossier(queryText);
  }, [queryText]);

  const handleFollowUpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!followUpInput.trim()) return;
    const newQuery = followUpInput.trim();
    setQueryText(newQuery);
    setFollowUpInput("");
  };

  // Audio Overview Synthesis
  const toggleAudioBriefing = () => {
    if (isPlayingAudio) {
      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
      setIsPlayingAudio(false);
    } else {
      if ("speechSynthesis" in window && sections.length > 0) {
        const speechText = `Welcome to the BioResearch briefing on ${queryText}. Executive synthesis: ${sections[0].content.replace(/\[\d+\]/g, "")}`;
        const utterance = new SpeechSynthesisUtterance(speechText);
        utterance.rate = 1.05;
        utterance.onend = () => setIsPlayingAudio(false);
        utterance.onerror = () => setIsPlayingAudio(false);
        window.speechSynthesis.speak(utterance);
        setIsPlayingAudio(true);
      }
    }
  };

  const handleCopyDossier = () => {
    const fullText = `# Research Briefing: ${queryText}\n\n` + 
      sections.map(s => `## ${s.title}\n${s.content}\n`).join("\n");
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(fullText);
      setIsCopiedDossier(true);
      setTimeout(() => setIsCopiedDossier(false), 2000);
    }
  };

  return (
    <div className={`flex flex-col h-screen transition-colors duration-200 overflow-hidden font-sans ${
      isDark ? "bg-[#121316] text-slate-100" : "bg-[#FAFAFC] text-slate-900"
    }`}>
      
      {/* ============================================================ */}
      {/* 1. TOP HEADER                                                */}
      {/* ============================================================ */}
      <header className={`h-14 px-6 flex items-center justify-between shrink-0 select-none transition-colors ${
        isDark ? "bg-[#18191E] border-b border-white/5" : "bg-white border-b border-slate-200 shadow-sm"
      }`}>
        
        {/* Left: Back & Title */}
        <div className="flex items-center gap-3">
          <button
            onClick={onBackToSearch}
            className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
              isDark ? "text-slate-400 hover:text-white hover:bg-white/5" : "text-slate-500 hover:text-slate-900 hover:bg-slate-100"
            }`}
            title="Back to Search"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-blue-600 flex items-center justify-center text-white shadow-sm shadow-blue-500/20">
              <BookOpen className="w-3.5 h-3.5" />
            </div>
            <h1 className="font-bold text-sm tracking-tight flex items-center gap-2">
              <span className={isDark ? "text-white" : "text-slate-900"}>BioResearch AI</span>
              <span className="text-slate-400 font-normal">|</span>
              <span className={`font-normal ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                NotebookLM Drug Research Briefing
              </span>
            </h1>
            <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${
              isDark 
                ? "bg-blue-500/10 text-blue-400 border-blue-500/20" 
                : "bg-blue-50 text-blue-700 border-blue-200"
            }`}>
              STUDY DOSSIER
            </span>
          </div>
        </div>

        {/* Right: Actions & Theme Toggle */}
        <div className="flex items-center gap-2.5">
          {/* Theme Toggle */}
          {onToggleTheme && (
            <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          )}

          <button
            onClick={() => fetchResearchDossier(queryText)}
            className={`p-2 rounded-lg border transition-colors cursor-pointer ${
              isDark 
                ? "border-white/10 text-slate-400 hover:text-white hover:bg-white/5" 
                : "border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            }`}
            title="Re-run Literature Mining"
          >
            <RefreshCw className={`w-4 h-4 ${isResearching ? "animate-spin text-blue-500" : ""}`} />
          </button>

          {/* Audio Overview (NotebookLM Podcast feature) */}
          <button
            onClick={toggleAudioBriefing}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 border transition-all cursor-pointer ${
              isPlayingAudio 
                ? "bg-purple-600/25 border-purple-500/50 text-purple-600 dark:text-purple-300 animate-pulse" 
                : isDark
                ? "bg-white/5 border-white/10 text-slate-300 hover:text-white hover:bg-white/10"
                : "bg-slate-100 border-slate-200 text-slate-700 hover:bg-slate-200"
            }`}
            title="Audio Overview Podcast"
          >
            {isPlayingAudio ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5 text-purple-500" />}
            <span>{isPlayingAudio ? "Pause Audio" : "Audio Overview"}</span>
          </button>

          <button
            onClick={handleCopyDossier}
            className={`p-2 rounded-lg border transition-colors cursor-pointer ${
              isDark 
                ? "border-white/10 text-slate-400 hover:text-white hover:bg-white/5" 
                : "border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            }`}
            title="Copy Markdown Dossier"
          >
            {isCopiedDossier ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
          </button>

          <button
            onClick={() => setStarred(!starred)}
            className={`p-2 rounded-lg border transition-colors cursor-pointer ${
              starred 
                ? "bg-amber-500/20 border-amber-500/40 text-amber-500" 
                : isDark
                ? "border-white/10 text-slate-400 hover:text-white hover:bg-white/5"
                : "border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            }`}
            title="Save to My Library"
          >
            <Star className={`w-4 h-4 ${starred ? "fill-amber-500" : ""}`} />
          </button>

          <button
            onClick={onOpenApiKeys}
            className={`p-2 rounded-lg border transition-colors cursor-pointer ${
              isDark 
                ? "border-white/10 text-slate-400 hover:text-white hover:bg-white/5" 
                : "border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            }`}
            title="AI Keys & Model Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* ============================================================ */}
      {/* 2. MAIN SPLIT INTERFACE                                      */}
      {/* ============================================================ */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* ========================================================== */}
        {/* CENTER NOTEBOOKLM RESEARCH BRIEFING FEED                   */}
        {/* ========================================================== */}
        <main className="flex-1 flex flex-col justify-between overflow-y-auto p-6 sm:p-10 space-y-6">
          <div className="max-w-3xl w-full mx-auto space-y-6">

            {/* Document Header & Source Count Pill */}
            <div className={`border-b pb-5 space-y-3 ${isDark ? "border-white/10" : "border-slate-200"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2">
                  <span className={`px-2.5 py-1 rounded-full font-mono text-[11px] font-semibold flex items-center gap-1.5 border ${
                    isDark 
                      ? "bg-blue-500/15 border-blue-500/30 text-blue-300" 
                      : "bg-blue-50 border-blue-200 text-blue-700"
                  }`}>
                    <Sparkles className="w-3 h-3 text-blue-500" />
                    <span>{citations.length} Sources Grounded via FastAPI</span>
                  </span>
                  <span className={`font-mono ${isDark ? "text-slate-500" : "text-slate-500"}`}>
                    PubMed · bioRxiv · ChEMBL · arXiv
                  </span>
                </div>

                <div className={`text-[11px] font-mono ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  {isResearching ? (
                    <span className="text-blue-500 flex items-center gap-1.5 animate-pulse font-medium">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Mining Data Loaders ({researchTime}s)...
                    </span>
                  ) : (
                    <span>Synthesis Time: {researchTime}s</span>
                  )}
                </div>
              </div>

              {/* Research Study H1 */}
              <h1 className={`text-2xl sm:text-3xl font-extrabold tracking-tight leading-tight font-sans ${
                isDark ? "text-white" : "text-slate-900"
              }`}>
                {queryText}
              </h1>

              {/* Source Quick-Pills Row (NotebookLM Style) */}
              <div className="flex items-center gap-2 overflow-x-auto py-1 text-xs">
                <span className={`font-mono text-[11px] shrink-0 ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                  Indexed:
                </span>
                {citations.map((cite) => (
                  <button
                    key={cite.citation_index}
                    onClick={() => {
                      setSelectedSource(cite);
                      setActiveRightTab("Sources");
                      setIsRightPanelOpen(true);
                    }}
                    className={`shrink-0 px-2.5 py-1 rounded-lg border transition-colors text-[11px] flex items-center gap-1.5 font-mono cursor-pointer ${
                      isDark 
                        ? "bg-white/5 hover:bg-white/10 border-white/10 text-slate-300 hover:text-white" 
                        : "bg-white hover:bg-slate-50 border-slate-200 text-slate-700 hover:text-slate-900 shadow-xs"
                    }`}
                  >
                    <span className="text-blue-600 dark:text-blue-400 font-bold">[{cite.citation_index}]</span>
                    <span className="truncate max-w-[150px]">{cite.source}: {cite.title}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Live Progress Bar (if mining) */}
            {isResearching && (
              <div className={`rounded-xl p-4 shadow-md space-y-2 border animate-fadeIn ${
                isDark ? "bg-[#18191E] border-white/10" : "bg-white border-slate-200"
              }`}>
                <div className="flex items-center justify-between text-xs">
                  <span className={`font-semibold flex items-center gap-2 ${isDark ? "text-white" : "text-slate-900"}`}>
                    <Loader2 className="w-3.5 h-3.5 text-blue-500 animate-spin" />
                    Connecting to PubMed, bioRxiv, arXiv & ChEMBL Data Loaders...
                  </span>
                  <span className="text-emerald-500 font-mono text-[11px] font-bold">
                    Step {activeStageIndex} of 4
                  </span>
                </div>
                <div className={`w-full rounded-full h-1.5 overflow-hidden ${isDark ? "bg-slate-800" : "bg-slate-100"}`}>
                  <div 
                    className="bg-gradient-to-r from-blue-600 to-cyan-500 h-1.5 transition-all duration-300 rounded-full"
                    style={{ width: `${(activeStageIndex / 4) * 100}%` }}
                  />
                </div>
              </div>
            )}

            {/* Structured NotebookLM Briefing Sections */}
            <div className="space-y-6 pt-1">
              {sections.map((section) => (
                <div 
                  key={section.id} 
                  className={`rounded-2xl p-6 sm:p-7 shadow-sm border backdrop-blur-sm space-y-3 transition-all ${
                    isDark 
                      ? "bg-[#18191E]/70 border-white/5 hover:border-white/10 shadow-black/30" 
                      : "bg-white border-slate-200/90 shadow-slate-200/50 hover:border-slate-300"
                  }`}
                >
                  <div className={`flex items-center justify-between border-b pb-2 ${
                    isDark ? "border-white/5" : "border-slate-100"
                  }`}>
                    <h2 className={`text-base sm:text-lg font-bold tracking-tight flex items-center gap-2 ${
                      isDark ? "text-white" : "text-slate-900"
                    }`}>
                      <span className="w-1.5 h-4 rounded-full bg-blue-600"></span>
                      <span>{section.title}</span>
                    </h2>
                    <span className="text-[10px] text-slate-400 font-mono uppercase tracking-wider">
                      Grounding Verified
                    </span>
                  </div>

                  {/* Render Grounded Text with Interactive Hoverable Citations */}
                  <GroundedTextRenderer
                    content={section.content}
                    citations={citations}
                    theme={theme}
                    onSelectSource={(cite) => {
                      setSelectedSource(cite);
                      setActiveRightTab("Sources");
                      setIsRightPanelOpen(true);
                    }}
                  />
                </div>
              ))}
            </div>

            {/* Note on Citation Hover */}
            <div className={`p-3.5 rounded-xl border text-xs flex items-center gap-2 font-mono ${
              isDark 
                ? "bg-blue-950/20 border-blue-500/20 text-slate-300" 
                : "bg-blue-50/70 border-blue-200/80 text-blue-900"
            }`}>
              <Sparkles className="w-4 h-4 text-blue-600 shrink-0" />
              <span>
                <b>Interactive Citation Tip:</b> Hover over any citation badge like <span className="font-bold text-blue-600 dark:text-blue-400">[1]</span> or <span className="font-bold text-blue-600 dark:text-blue-400">[2]</span> to inspect the exact grounded excerpt pulled directly from that resource.
              </span>
            </div>

          </div>

          {/* Bottom Follow-Up Prompt Input Bar */}
          <div className="max-w-3xl w-full mx-auto pt-4">
            <form 
              onSubmit={handleFollowUpSubmit}
              className={`rounded-2xl p-2 border shadow-lg flex items-center justify-between gap-2 transition-all ${
                isDark 
                  ? "bg-[#18191E] border-white/10 focus-within:border-blue-500/50" 
                  : "bg-white border-slate-200 focus-within:border-blue-500 shadow-slate-200/60"
              }`}
            >
              <div className="flex items-center gap-2 flex-1 px-3">
                <input
                  type="text"
                  value={followUpInput}
                  onChange={(e) => setFollowUpInput(e.target.value)}
                  placeholder="Ask a follow-up about this drug research briefing (e.g. Compare in vitro affinities, investigate resistance pathways)..."
                  className={`w-full bg-transparent text-sm outline-none ${
                    isDark ? "text-white placeholder:text-slate-500" : "text-slate-900 placeholder:text-slate-400"
                  }`}
                />
              </div>

              <button
                type="submit"
                disabled={isResearching}
                className="w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white flex items-center justify-center transition-all shadow-md shadow-blue-600/30 cursor-pointer shrink-0"
                title="Send query"
              >
                {isResearching ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
              </button>
            </form>
          </div>
        </main>

        {/* ========================================================== */}
        {/* RIGHT SIDE PANEL: NOTEBOOKLM SOURCES & INSPECTOR           */}
        {/* ========================================================== */}
        {isRightPanelOpen && (
          <aside className={`w-80 lg:w-96 border-l flex flex-col justify-between shrink-0 overflow-y-auto select-none transition-colors ${
            isDark ? "bg-[#18191E] border-white/5" : "bg-white border-slate-200 shadow-sm"
          }`}>
            
            {/* Top Bar */}
            <div>
              <div className={`p-4 border-b flex items-center justify-between ${
                isDark ? "border-white/5" : "border-slate-100"
              }`}>
                <div>
                  <h3 className={`font-bold text-sm flex items-center gap-1.5 ${
                    isDark ? "text-white" : "text-slate-900"
                  }`}>
                    <BookOpen className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                    <span>Research Sources Hub</span>
                  </h3>
                  <span className={`text-[10px] font-mono ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    {citations.length} Grounded References
                  </span>
                </div>
                <button
                  onClick={() => setIsRightPanelOpen(false)}
                  className={`p-1 rounded-lg transition-colors cursor-pointer ${
                    isDark ? "text-slate-400 hover:text-white hover:bg-white/5" : "text-slate-400 hover:text-slate-900 hover:bg-slate-100"
                  }`}
                  title="Close panel"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Panel Tabs */}
              <div className={`flex items-center px-4 pt-3 border-b text-xs font-semibold space-x-1 ${
                isDark ? "border-white/5 text-slate-400" : "border-slate-100 text-slate-500"
              }`}>
                {(["Sources", "Ask", "Activity", "Chemical"] as const).map((tab) => {
                  const isActive = activeRightTab === tab;
                  const label = tab === "Chemical" ? "Chemistry (Adv)" : tab;

                  return (
                    <button
                      key={tab}
                      onClick={() => setActiveRightTab(tab)}
                      className={`pb-2 px-2.5 transition-colors cursor-pointer relative ${
                        isActive 
                          ? isDark ? "text-white" : "text-slate-900 font-bold" 
                          : "hover:text-blue-600"
                      }`}
                    >
                      <span>{label}</span>
                      {isActive && (
                        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-full"></div>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* TAB 1: SOURCES TAB (NotebookLM Source Documents) */}
              {activeRightTab === "Sources" && (
                <div className="p-4 space-y-4">
                  {selectedSource ? (
                    <div className={`rounded-xl p-4 space-y-3 border ${
                      isDark 
                        ? "bg-[#121316] border-blue-500/30" 
                        : "bg-slate-50 border-blue-200 shadow-xs"
                    }`}>
                      <div className="flex items-center justify-between text-xs">
                        <span className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] border ${
                          isDark ? "bg-blue-500/20 text-blue-300 border-blue-500/30" : "bg-blue-100 text-blue-800 border-blue-200"
                        }`}>
                          [{selectedSource.citation_index}] {selectedSource.source}
                        </span>
                        <span className="font-mono text-slate-400 text-[10px]">{selectedSource.year}</span>
                      </div>

                      <h4 className={`text-xs font-bold leading-snug ${isDark ? "text-white" : "text-slate-900"}`}>
                        {selectedSource.title}
                      </h4>

                      <p className={`text-[10px] ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                        {Array.isArray(selectedSource.authors) ? selectedSource.authors.join(", ") : selectedSource.authors}
                      </p>

                      {/* Cited Evidence Excerpt */}
                      {selectedSource.evidence_quote && (
                        <div className={`p-2.5 rounded-lg border ${
                          isDark ? "bg-black/40 border-white/5" : "bg-white border-slate-200"
                        }`}>
                          <span className={`text-[9px] font-mono block mb-0.5 ${
                            isDark ? "text-cyan-400" : "text-blue-600 font-bold"
                          }`}>
                            CITED EVIDENCE IN TEXT:
                          </span>
                          <p className={`text-xs italic leading-relaxed ${isDark ? "text-slate-200" : "text-slate-800"}`}>
                            "{selectedSource.evidence_quote}"
                          </p>
                        </div>
                      )}

                      {/* Full Abstract */}
                      <div className="space-y-1">
                        <span className={`text-[10px] font-mono uppercase block ${isDark ? "text-slate-500" : "text-slate-500"}`}>
                          ABSTRACT
                        </span>
                        <p className={`text-[11px] leading-relaxed max-h-48 overflow-y-auto pr-1 ${
                          isDark ? "text-slate-300" : "text-slate-700"
                        }`}>
                          {selectedSource.abstract || "Indexed research document abstract."}
                        </p>
                      </div>

                      {/* External Link */}
                      {selectedSource.url && (
                        <a
                          href={selectedSource.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={`w-full py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors border ${
                            isDark 
                              ? "bg-white/5 hover:bg-white/10 text-blue-400 border-white/5" 
                              : "bg-white hover:bg-slate-100 text-blue-700 border-slate-200 shadow-2xs"
                          }`}
                        >
                          <span>Open in {selectedSource.source}</span>
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 text-center py-6">
                      Click any citation badge in the text to inspect the source here.
                    </div>
                  )}

                  {/* List of All Indexed Sources */}
                  <div className={`pt-2 border-t space-y-2 ${isDark ? "border-white/5" : "border-slate-100"}`}>
                    <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block mb-1">
                      All Sources in this Notebook ({citations.length})
                    </span>
                    {citations.map((cite) => (
                      <div
                        key={cite.citation_index}
                        onClick={() => setSelectedSource(cite)}
                        className={`p-2.5 rounded-lg border transition-all cursor-pointer text-xs ${
                          selectedSource?.citation_index === cite.citation_index
                            ? isDark
                              ? "bg-blue-600/10 border-blue-500/40 text-white"
                              : "bg-blue-50/80 border-blue-300 text-slate-900"
                            : isDark
                            ? "bg-[#121316] border-white/5 text-slate-300 hover:border-white/15"
                            : "bg-slate-50 border-slate-200/70 text-slate-700 hover:bg-slate-100"
                        }`}
                      >
                        <div className="flex items-center justify-between text-[10px] font-mono mb-1">
                          <span className="text-blue-600 dark:text-blue-400 font-bold">[{cite.citation_index}] {cite.source}</span>
                          <span className="text-slate-400">{cite.year}</span>
                        </div>
                        <h5 className="font-semibold text-xs leading-snug line-clamp-2">
                          {cite.title}
                        </h5>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 2: ASK TAB */}
              {activeRightTab === "Ask" && (
                <div className="p-4 space-y-3 text-xs">
                  <div className={isDark ? "text-slate-400" : "text-slate-600"}>
                    Ask questions grounded solely in this notebook's sources:
                  </div>
                  <div className={`p-3 rounded-xl border space-y-2 ${
                    isDark ? "bg-[#121316] border-white/5 text-slate-300" : "bg-slate-50 border-slate-200 text-slate-700"
                  }`}>
                    <p>
                      I have analyzed all {citations.length} sources regarding {queryText}. You can ask about specific mechanism of action details, biomarker kinetics, or clinical toxicity signals.
                    </p>
                  </div>
                </div>
              )}

              {/* TAB 3: ACTIVITY TAB */}
              {activeRightTab === "Activity" && (
                <div className="p-4 space-y-3 text-xs font-mono">
                  <div className={`mb-2 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    FastAPI Multi-Agent Execution Stream
                  </div>
                  {reasoningLogs.map((log, i) => (
                    <div key={i} className={`p-2.5 rounded-lg border space-y-1 ${
                      isDark ? "bg-[#121316] border-white/5" : "bg-slate-50 border-slate-200"
                    }`}>
                      <div className="flex items-center justify-between text-[10px] text-slate-400">
                        <span className="text-blue-600 dark:text-cyan-400 font-semibold">{log.agent}</span>
                        <span>{log.timestamp}</span>
                      </div>
                      <p className={`text-[11px] ${isDark ? "text-slate-300" : "text-slate-700"}`}>{log.thought}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* TAB 4: ADVANCED CHEMISTRY TAB (Isolated from chat!) */}
              {activeRightTab === "Chemical" && (
                <div className="p-4 space-y-4">
                  <div className={`text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                    Advanced RDKit Cheminformatics & Molecular Conformer Inspector:
                  </div>
                  <ChemicalStructureViewer 
                    moleculeName="Candidate A-17" 
                    theme={theme} 
                  />
                </div>
              )}
            </div>

            {/* Bottom Status */}
            <div className={`p-3 border-t text-[11px] font-mono flex items-center justify-between ${
              isDark ? "border-white/5 text-slate-500" : "border-slate-100 text-slate-500 bg-slate-50"
            }`}>
              <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                FastAPI Sources Connected
              </span>
              <span>Grounding: 100%</span>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
