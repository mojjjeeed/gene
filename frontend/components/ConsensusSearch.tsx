"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Plus,
  Home,
  BookMarked,
  History,
  Search,
  Network,
  Atom,
  ExternalLink,
  Mic,
  ArrowRight,
  Sparkles,
  ChevronDown,
  ArrowLeft,
  Key,
  FileText,
  FlaskConical,
  MessageSquare,
  Activity,
} from "lucide-react";
import ThemeToggle from "./ThemeToggle";

interface ConsensusSearchProps {
  onSearch: (query: string) => void;
  onBackToLanding: () => void;
  onOpenApiKeys: () => void;
  theme?: "light" | "dark";
  onToggleTheme?: () => void;
}

const DEFAULT_QUERY =
  "Find novel small molecules related to EGFR target and explain why each candidate is worth investigating.";

const RECENT_CHATS = [
  "Drug Discovery Using Autonomous AI Agents",
  "EGFR T790M / C797S Kinase Inhibitor Scaffolds",
  "KRAS G12D Allosteric Pocket Covalent Ligands",
  "Alzheimer's BACE1 & Tau Dual Blockers",
];

const PRESET_QUERIES = [
  { label: "Run a deep review", query: "Run a Deep review on allosteric kinase inhibitors in drug-resistant NSCLC" },
  { label: "Find studies by method", query: "Find studies by method evaluating RDKit and cryogenic electron microscopy for small molecule docking" },
  { label: "Draft a report", query: "Draft an executive synthesis report on novel covalent warheads targeting Cys797" },
  { label: "Novel small molecules for EGFR", query: DEFAULT_QUERY },
];

const SKILLS = [
  "Target-to-Molecule",
  "Literature Extraction",
  "Lipinski Ro5 & ADMET",
  "In Silico Docking",
  "Covalent Warhead Screening",
];

const SEARCHED_SOURCES = "PubMed · bioRxiv · arXiv · ChEMBL · PubChem · ClinicalTrials.gov";

// Lightweight keyword spotting so the UI can echo back what it recognised while the user types.
const KNOWN_TOPICS: { keywords: string[]; label: string; tone: "blue" | "amber" | "purple" }[] = [
  { keywords: ["egfr", "t790m", "c797s", "osimertinib"], label: "EGFR kinase", tone: "blue" },
  { keywords: ["kras", "g12d", "g12c", "pancrea"], label: "KRAS oncoprotein", tone: "amber" },
  { keywords: ["alzheimer", "bace1", "amyloid", "tau"], label: "BACE1 / amyloid-beta", tone: "purple" },
];

// Minimal typing for the (still vendor-prefixed) Web Speech API
interface SpeechRecognitionLike {
  onresult: ((evt: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getSpeechRecognition(): SpeechRecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export default function ConsensusSearch({
  onSearch,
  onBackToLanding,
  onOpenApiKeys,
  theme = "dark",
  onToggleTheme,
}: ConsensusSearchProps) {
  const isDark = theme === "dark";
  const pick = (dark: string, light: string) => (isDark ? dark : light);

  const [queryInput, setQueryInput] = useState("");
  const [isDeepMode, setIsDeepMode] = useState(true);
  const [selectedSkill, setSelectedSkill] = useState(SKILLS[0]);
  const [showSkillDropdown, setShowSkillDropdown] = useState(false);
  const [isListeningVoice, setIsListeningVoice] = useState(false);
  const [voiceNotice, setVoiceNotice] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const skillRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  const detected = useMemo(() => {
    const q = queryInput.toLowerCase();
    return KNOWN_TOPICS.find((t) => t.keywords.some((k) => q.includes(k))) ?? null;
  }, [queryInput]);

  // Close the skills menu on outside click / Escape
  useEffect(() => {
    if (!showSkillDropdown) return;
    const onDown = (e: MouseEvent) => {
      if (!skillRef.current?.contains(e.target as Node)) setShowSkillDropdown(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowSkillDropdown(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [showSkillDropdown]);

  // Stop the microphone if we leave the screen mid-dictation
  useEffect(() => () => recognitionRef.current?.stop(), []);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    onSearch(queryInput.trim() || DEFAULT_QUERY);
  };

  const launch = (query: string) => {
    setQueryInput(query);
    onSearch(query);
  };

  const toggleVoice = () => {
    if (isListeningVoice) {
      recognitionRef.current?.stop();
      setIsListeningVoice(false);
      return;
    }
    const Ctor = getSpeechRecognition();
    if (!Ctor) {
      setVoiceNotice("Voice input isn't supported in this browser. Try Chrome or Safari.");
      return;
    }
    setVoiceNotice("");
    try {
      const rec = new Ctor();
      rec.onresult = (evt) => {
        setQueryInput(evt.results[0][0].transcript);
        inputRef.current?.focus();
      };
      rec.onerror = () => {
        setIsListeningVoice(false);
        setVoiceNotice("Couldn't hear anything. Check microphone permissions and try again.");
      };
      rec.onend = () => setIsListeningVoice(false);
      recognitionRef.current = rec;
      rec.start();
      setIsListeningVoice(true);
    } catch {
      setVoiceNotice("Voice input couldn't start. Please type your query instead.");
    }
  };

  const toneClasses = {
    blue: pick("bg-blue-500/10 border-blue-500/30 text-blue-300", "bg-blue-50 border-blue-200 text-blue-700"),
    amber: pick("bg-amber-500/10 border-amber-500/30 text-amber-300", "bg-amber-50 border-amber-200 text-amber-700"),
    purple: pick("bg-purple-500/10 border-purple-500/30 text-purple-300", "bg-purple-50 border-purple-200 text-purple-700"),
  };

  const sidebarItem = `w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs transition-colors text-left ${pick(
    "text-slate-400 hover:text-white hover:bg-white/5",
    "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
  )}`;
  const sidebarItemDisabled = `w-full flex items-center justify-between gap-2.5 px-3 py-2 rounded-lg text-xs text-left opacity-60 ${pick("text-slate-400", "text-slate-600")}`;
  const sectionLabel = `text-[10px] font-semibold uppercase tracking-wider px-3 block mb-1 ${pick("text-slate-500", "text-slate-400")}`;

  return (
    <div
      className={`flex h-dvh overflow-hidden font-sans transition-colors duration-200 ${pick(
        "bg-[#18191E] text-slate-200",
        "bg-[#FAFAFC] text-slate-800"
      )}`}
    >
      {/* ============================ SIDEBAR (md+) ============================ */}
      <aside
        className={`hidden md:flex w-64 border-r flex-col justify-between shrink-0 select-none transition-colors ${pick(
          "bg-[#121316] border-white/5",
          "bg-white border-slate-200"
        )}`}
      >
        <div className="p-4 space-y-4 overflow-y-auto">
          <div className="flex items-center justify-between pb-2">
            <button type="button" onClick={onBackToLanding} className="flex items-center gap-2.5 text-left group">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-md shadow-blue-500/20 group-hover:scale-105 transition-transform">
                <Atom className="w-5 h-5 text-slate-950" aria-hidden="true" />
              </div>
              <div>
                <span className={`font-bold text-sm tracking-tight block ${pick("text-white", "text-slate-900")}`}>BioResearch AI</span>
                <span className={`text-[10px] font-mono ${pick("text-slate-500", "text-slate-400")}`}>Research workspace</span>
              </div>
            </button>

            <button
              type="button"
              onClick={onBackToLanding}
              className={`p-1.5 rounded-lg transition-colors ${pick("text-slate-500 hover:text-slate-300 hover:bg-white/5", "text-slate-400 hover:text-slate-700 hover:bg-slate-100")}`}
              aria-label="Back to landing page"
              title="Back to landing page"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
          </div>

          <button
            type="button"
            onClick={() => {
              setQueryInput("");
              inputRef.current?.focus();
            }}
            className={`w-full py-2 px-3 rounded-lg border text-xs font-semibold flex items-center gap-2 transition-all ${pick(
              "bg-blue-600/15 hover:bg-blue-600/25 border-blue-500/30 text-blue-400",
              "bg-blue-50 hover:bg-blue-100 border-blue-200 text-blue-700"
            )}`}
          >
            <Plus className="w-4 h-4" aria-hidden="true" />
            New search
          </button>

          <nav className="space-y-1" aria-label="Workspace">
            <button
              type="button"
              aria-current="page"
              onClick={() => inputRef.current?.focus()}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium ${pick("bg-white/5 text-white", "bg-slate-100 text-slate-900")}`}
            >
              <Home className="w-4 h-4 text-cyan-500" aria-hidden="true" />
              Home
            </button>
            <div className={sidebarItemDisabled} aria-disabled="true" title="Coming soon">
              <span className="flex items-center gap-2.5">
                <BookMarked className="w-4 h-4" aria-hidden="true" /> My Library
              </span>
              <span className="text-[9px] font-mono uppercase tracking-wider">Soon</span>
            </div>
            <div className={sidebarItemDisabled} aria-disabled="true" title="Coming soon">
              <span className="flex items-center gap-2.5">
                <History className="w-4 h-4" aria-hidden="true" /> History
              </span>
              <span className="text-[9px] font-mono uppercase tracking-wider">Soon</span>
            </div>
          </nav>

          <div>
            <span className={sectionLabel}>Example searches</span>
            <div className="space-y-0.5">
              {RECENT_CHATS.map((title) => (
                <button key={title} type="button" onClick={() => launch(title)} className={`${sidebarItem} !py-1.5`}>
                  <MessageSquare className="w-3.5 h-3.5 text-slate-400 shrink-0" aria-hidden="true" />
                  <span className="truncate">{title}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <span className={sectionLabel}>Tools</span>
            <div className="space-y-0.5">
              <button type="button" onClick={() => inputRef.current?.focus()} className={`${sidebarItem} !py-1.5`}>
                <Search className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
                Paper search
              </button>
              <div className={`${sidebarItemDisabled} !py-1.5`} aria-disabled="true" title="Coming soon">
                <span className="flex items-center gap-2.5">
                  <Network className="w-3.5 h-3.5" aria-hidden="true" /> Citation graph
                </span>
                <span className="text-[9px] font-mono uppercase tracking-wider">Soon</span>
              </div>
            </div>
          </div>
        </div>

        <div className={`p-4 border-t space-y-3 ${pick("border-white/5", "border-slate-100")}`}>
          <button
            type="button"
            onClick={onOpenApiKeys}
            className={`w-full flex items-center justify-between px-2 py-1.5 rounded text-xs transition-colors ${pick("text-slate-400 hover:text-white hover:bg-white/5", "text-slate-600 hover:text-slate-900 hover:bg-slate-100")}`}
          >
            <span className="flex items-center gap-1.5">
              <Key className="w-3 h-3 text-amber-500" aria-hidden="true" />
              AI provider keys
            </span>
            <ExternalLink className="w-3 h-3 text-slate-400" aria-hidden="true" />
          </button>

          <div className={`pt-3 border-t flex items-center justify-between ${pick("border-white/5", "border-slate-100")}`}>
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-white" aria-hidden="true">M</div>
              <span className={`text-xs font-medium ${pick("text-slate-200", "text-slate-800")}`}>Mohammed</span>
            </div>
            {onToggleTheme && <ThemeToggle theme={theme} onToggle={onToggleTheme} />}
          </div>
        </div>
      </aside>

      {/* ============================ MAIN ============================ */}
      <div className="flex-1 min-w-0 flex flex-col relative overflow-y-auto">
        {/* Compact top bar below md (sidebar is hidden there) */}
        <div className="md:hidden flex items-center justify-between px-4 py-3 shrink-0">
          <button type="button" onClick={onBackToLanding} className="flex items-center gap-2 text-sm font-bold">
            <ArrowLeft className="w-4 h-4" aria-hidden="true" />
            BioResearch AI
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onOpenApiKeys}
              aria-label="AI provider keys"
              className={`p-2 rounded-xl border transition-colors ${pick("border-white/10 text-slate-300 hover:bg-white/5", "border-slate-200 text-slate-600 hover:bg-slate-100")}`}
            >
              <Key className="w-4 h-4" />
            </button>
            {onToggleTheme && <ThemeToggle theme={theme} onToggle={onToggleTheme} />}
          </div>
        </div>

        {/* Background glow */}
        <div
          aria-hidden="true"
          className={`absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 rounded-full blur-3xl pointer-events-none ${pick("bg-cyan-600/10", "bg-blue-400/10")}`}
        />

        <main className="flex-1 flex flex-col justify-center px-4 sm:px-8 py-8 relative">
          <div className="max-w-2xl w-full mx-auto text-center space-y-6">
            <div className="flex flex-col items-center">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-cyan-400 to-blue-600 flex items-center justify-center shadow-xl shadow-cyan-500/20 mb-4">
                <Atom className="w-7 h-7 text-slate-950" aria-hidden="true" />
              </div>
              <h1 className={`text-2xl sm:text-3xl font-bold tracking-tight ${pick("text-white", "text-slate-900")}`}>BioResearch AI</h1>
              <p className={`text-xl sm:text-2xl font-semibold mt-1 ${pick("text-slate-300", "text-slate-700")}`}>Research starts here</p>
            </div>

            <div className="space-y-3">
              <form
                onSubmit={handleSubmit}
                className={`relative rounded-2xl p-2 shadow-2xl border transition-all text-left ${pick(
                  "bg-[#1E2026] border-white/10 focus-within:border-blue-500/60",
                  "bg-white border-slate-200 focus-within:border-blue-500 shadow-slate-200/80"
                )}`}
              >
                <label htmlFor="research-query" className="sr-only">
                  Research question
                </label>
                <input
                  id="research-query"
                  ref={inputRef}
                  type="text"
                  value={queryInput}
                  onChange={(e) => setQueryInput(e.target.value)}
                  placeholder="Ask a research question, e.g. novel small molecules for EGFR T790M"
                  autoComplete="off"
                  className={`w-full bg-transparent px-4 py-3 text-base sm:text-lg outline-none ${pick("text-slate-100 placeholder:text-slate-500", "text-slate-900 placeholder:text-slate-400")}`}
                  autoFocus
                />

                <div className={`flex items-center justify-between pt-2 px-2 border-t ${pick("border-white/5", "border-slate-100")}`}>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setQueryInput(DEFAULT_QUERY);
                        inputRef.current?.focus();
                      }}
                      className={`w-7 h-7 rounded-lg flex items-center justify-center transition-colors ${pick("bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white", "bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-900")}`}
                      aria-label="Insert example prompt"
                      title="Insert example prompt"
                    >
                      <Plus className="w-4 h-4" />
                    </button>

                    <div className="relative" ref={skillRef}>
                      <button
                        type="button"
                        onClick={() => setShowSkillDropdown((v) => !v)}
                        aria-haspopup="listbox"
                        aria-expanded={showSkillDropdown}
                        className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs transition-colors max-w-[9rem] ${pick("bg-white/5 hover:bg-white/10 text-slate-300", "bg-slate-100 hover:bg-slate-200 text-slate-700")}`}
                      >
                        <span className="truncate">{selectedSkill === SKILLS[0] ? "Skills" : selectedSkill}</span>
                        <ChevronDown className="w-3 h-3 text-slate-400 shrink-0" aria-hidden="true" />
                      </button>

                      {showSkillDropdown && (
                        <div
                          role="listbox"
                          aria-label="Skills"
                          className={`absolute left-0 bottom-full mb-2 w-60 rounded-xl shadow-xl p-1 z-30 text-xs border animate-fadeIn ${pick("bg-[#18191E] border-white/10", "bg-white border-slate-200")}`}
                        >
                          <p className={`px-2.5 pt-1.5 pb-1 text-[10px] ${pick("text-slate-500", "text-slate-400")}`}>
                            Preview. Not yet applied to search.
                          </p>
                          {SKILLS.map((skill) => (
                            <button
                              key={skill}
                              type="button"
                              role="option"
                              aria-selected={skill === selectedSkill}
                              onClick={() => {
                                setSelectedSkill(skill);
                                setShowSkillDropdown(false);
                              }}
                              className={`w-full text-left px-2.5 py-1.5 rounded-lg transition-colors flex items-center justify-between ${pick("text-slate-300 hover:bg-white/10 hover:text-white", "text-slate-700 hover:bg-slate-100 hover:text-slate-900")}`}
                            >
                              {skill}
                              {skill === selectedSkill && <span className="text-blue-500">✓</span>}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => setIsDeepMode((v) => !v)}
                      aria-pressed={isDeepMode}
                      title="Preview. Not yet applied to search."
                      className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
                        isDeepMode
                          ? pick("bg-blue-600/20 border-blue-500/40 text-blue-300", "bg-blue-50 border-blue-300 text-blue-700")
                          : pick("bg-white/5 border-white/10 text-slate-400", "bg-slate-100 border-slate-200 text-slate-600")
                      }`}
                    >
                      <Sparkles className="w-3 h-3 text-blue-500" aria-hidden="true" />
                      Deep
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={toggleVoice}
                      aria-pressed={isListeningVoice}
                      className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                        isListeningVoice
                          ? "bg-red-500/20 text-red-500 animate-pulse border border-red-500/40"
                          : pick("text-slate-400 hover:text-white hover:bg-white/5", "text-slate-500 hover:text-slate-900 hover:bg-slate-100")
                      }`}
                      aria-label={isListeningVoice ? "Stop voice input" : "Start voice input"}
                      title={isListeningVoice ? "Listening… click to stop" : "Voice input"}
                    >
                      <Mic className="w-4 h-4" />
                    </button>

                    <button
                      type="submit"
                      className="w-9 h-9 rounded-lg bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center shadow-lg shadow-blue-600/30 transition-all"
                      aria-label="Run research"
                      title="Run research"
                    >
                      <ArrowRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </form>

              {voiceNotice && (
                <p role="status" className={`text-xs text-left px-1 ${pick("text-amber-300", "text-amber-700")}`}>
                  {voiceNotice}
                </p>
              )}

              {/* What the search will do (no invented statistics) */}
              {queryInput.trim().length > 3 && (
                <button
                  type="button"
                  onClick={() => handleSubmit()}
                  className={`w-full p-3 rounded-xl border text-left transition-all animate-fadeIn hover:border-blue-500 ${
                    detected ? toneClasses[detected.tone] : pick("bg-white/5 border-white/10 text-slate-300", "bg-white border-slate-200 text-slate-700")
                  }`}
                >
                  <div className="flex items-center justify-between gap-3 text-xs mb-0.5">
                    <span className="font-bold flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5" aria-hidden="true" />
                      {detected ? `Recognised: ${detected.label}` : "Ready to search"}
                    </span>
                    <kbd className={`hidden sm:inline text-[10px] font-mono ${pick("text-slate-400", "text-slate-500")}`}>Press Enter ↵</kbd>
                  </div>
                  <p className={`text-[11px] ${pick("text-slate-400", "text-slate-500")}`}>Will search {SEARCHED_SOURCES}</p>
                </button>
              )}
            </div>

            {/* Suggestion chips */}
            <div className="flex flex-wrap items-center justify-center gap-2.5 pt-2">
              {PRESET_QUERIES.map((item, idx) => (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => launch(item.query)}
                  className={`px-3.5 py-1.5 rounded-xl border text-xs font-medium transition-all flex items-center gap-1.5 ${pick(
                    "bg-[#1E2026] hover:bg-[#262830] border-white/5 hover:border-white/15 text-slate-300",
                    "bg-white hover:bg-slate-50 border-slate-200 text-slate-700 hover:text-slate-900 shadow-xs"
                  )}`}
                >
                  {idx === 0 && <Sparkles className="w-3 h-3 text-cyan-500" aria-hidden="true" />}
                  {idx === 1 && <FlaskConical className="w-3 h-3 text-emerald-500" aria-hidden="true" />}
                  {idx === 2 && <FileText className="w-3 h-3 text-purple-500" aria-hidden="true" />}
                  {idx === 3 && <Atom className="w-3 h-3 text-blue-500" aria-hidden="true" />}
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </main>

        <p className={`text-center text-xs pb-4 relative ${pick("text-slate-500", "text-slate-400")}`}>
          Results come from public scientific databases. Verify against the original papers.
        </p>
      </div>
    </div>
  );
}
