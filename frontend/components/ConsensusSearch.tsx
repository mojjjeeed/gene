"use client";

import React, { useState, useMemo } from "react";
import { 
  Plus, 
  Home, 
  BookMarked, 
  History, 
  Search, 
  Network, 
  Atom, 
  ExternalLink, 
  SlidersHorizontal, 
  Mic, 
  ArrowRight, 
  Sparkles, 
  ChevronDown, 
  Zap, 
  ArrowLeft, 
  Key, 
  FileText, 
  FlaskConical, 
  MessageSquare,
  Activity
} from "lucide-react";
import ThemeToggle from "./ThemeToggle";

interface ConsensusSearchProps {
  onSearch: (query: string) => void;
  onBackToLanding: () => void;
  onOpenApiKeys: () => void;
  theme?: "light" | "dark";
  onToggleTheme?: () => void;
}

const RECENT_CHATS = [
  "Drug Discovery Using Autonomous AI Agents",
  "EGFR T790M / C797S Kinase Inhibitor Scaffolds",
  "KRAS G12D Allosteric Pocket Covalent Ligands",
  "Alzheimer's BACE1 & Tau Dual Blockers"
];

const PRESET_QUERIES = [
  { label: "Run a Deep review", query: "Run a Deep review on allosteric kinase inhibitors in drug-resistant NSCLC" },
  { label: "Find studies by method", query: "Find studies by method evaluating RDKit and cryogenic electron microscopy for small molecule docking" },
  { label: "Draft a report", query: "Draft an executive synthesis report on novel covalent warheads targeting Cys797" },
  { label: "Find novel small molecules for EGFR", query: "Find novel small molecules related to EGFR target and explain why each candidate is worth investigating." }
];

export default function ConsensusSearch({
  onSearch,
  onBackToLanding,
  onOpenApiKeys,
  theme = "dark",
  onToggleTheme
}: ConsensusSearchProps) {
  const [queryInput, setQueryInput] = useState("");
  const [isDeepMode, setIsDeepMode] = useState(true);
  const [selectedSkill, setSelectedSkill] = useState("Target-to-Molecule");
  const [showSkillDropdown, setShowSkillDropdown] = useState(false);
  const [isListeningVoice, setIsListeningVoice] = useState(false);

  const isDark = theme === "dark";

  // Real-time Bio-NER Target & Literature Intelligence while typing
  const liveTargetDetection = useMemo(() => {
    const q = queryInput.toLowerCase().trim();
    if (!q) return null;

    if (q.includes("egfr") || q.includes("t790m") || q.includes("c797s") || q.includes("osimertinib") || q.includes("lung")) {
      return {
        target: "EGFR Kinase Domain (T790M/C797S)",
        modality: "4th-Gen Reversible & Allosteric Small Molecules",
        pubmedHits: "1,420+ papers",
        chemblCompounds: "4,800 bioactivity points",
        status: "Active Oncology Target",
        color: isDark ? "text-blue-400" : "text-blue-700",
        badgeBg: isDark ? "bg-blue-500/10 border-blue-500/30" : "bg-blue-50 border-blue-200"
      };
    } else if (q.includes("kras") || q.includes("g12d") || q.includes("g12c") || q.includes("pancrea")) {
      return {
        target: "KRAS G12D Oncoprotein (Switch-II Pocket)",
        modality: "Targeted Covalent & Allosteric Pocket Inactivators",
        pubmedHits: "890+ papers",
        chemblCompounds: "1,200 bioactivity points",
        status: "High-Priority Pancreatic Oncology",
        color: isDark ? "text-amber-400" : "text-amber-700",
        badgeBg: isDark ? "bg-amber-500/10 border-amber-500/30" : "bg-amber-50 border-amber-200"
      };
    } else if (q.includes("alzheimer") || q.includes("bace1") || q.includes("amyloid") || q.includes("tau")) {
      return {
        target: "BACE1 & Amyloid Beta Oligomerization",
        modality: "Blood-Brain Barrier Permeable Dual Inhibitors",
        pubmedHits: "3,100+ papers",
        chemblCompounds: "6,200 bioactivity points",
        status: "Neurodegenerative Target",
        color: isDark ? "text-purple-400" : "text-purple-700",
        badgeBg: isDark ? "bg-purple-500/10 border-purple-500/30" : "bg-purple-50 border-purple-200"
      };
    } else if (q.length > 5) {
      return {
        target: `Target Entity: ${queryInput.slice(0, 28)}...`,
        modality: "Multi-Agent Literature Mining & De Novo Cheminformatics",
        pubmedHits: "Searching PubMed & bioRxiv...",
        chemblCompounds: "Querying ChEMBL database...",
        status: "Custom Biomedical Inquiry",
        color: isDark ? "text-cyan-400" : "text-blue-700",
        badgeBg: isDark ? "bg-cyan-500/10 border-cyan-500/30" : "bg-blue-50 border-blue-200"
      };
    }
    return null;
  }, [queryInput, isDark]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const finalQuery = queryInput.trim() || "Find novel small molecules related to EGFR target and explain why each candidate is worth investigating.";
    onSearch(finalQuery);
  };

  const handleChipClick = (query: string) => {
    setQueryInput(query);
    onSearch(query);
  };

  // Mock voice search activation
  const toggleVoice = () => {
    if (!isListeningVoice) {
      setIsListeningVoice(true);
      if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
        try {
          const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
          const rec = new SpeechRec();
          rec.onresult = (evt: any) => {
            const transcript = evt.results[0][0].transcript;
            setQueryInput(transcript);
            setIsListeningVoice(false);
          };
          rec.onerror = () => setIsListeningVoice(false);
          rec.onend = () => setIsListeningVoice(false);
          rec.start();
        } catch {
          setTimeout(() => {
            setQueryInput("Find novel small molecules related to EGFR T790M resistance");
            setIsListeningVoice(false);
          }, 1500);
        }
      } else {
        setTimeout(() => {
          setQueryInput("Find novel small molecules related to EGFR T790M resistance");
          setIsListeningVoice(false);
        }, 1200);
      }
    } else {
      setIsListeningVoice(false);
    }
  };

  return (
    <div className={`flex h-screen overflow-hidden font-sans transition-colors duration-200 ${
      isDark ? "bg-[#18191E] text-slate-200" : "bg-[#FAFAFC] text-slate-800"
    }`}>
      
      {/* ============================================================ */}
      {/* 1. LEFT SIDEBAR                                              */}
      {/* ============================================================ */}
      <aside className={`w-64 border-r flex flex-col justify-between shrink-0 select-none transition-colors ${
        isDark ? "bg-[#121316] border-white/5" : "bg-white border-slate-200 shadow-sm"
      }`}>
        
        {/* Top Section */}
        <div className="p-4 space-y-4">
          
          {/* Logo & Workspace Brand */}
          <div className="flex items-center justify-between pb-2">
            <button 
              onClick={onBackToLanding}
              className="flex items-center gap-2.5 text-left group cursor-pointer"
            >
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center text-slate-950 font-black shadow-md shadow-blue-500/20 group-hover:scale-105 transition-transform">
                <Atom className="w-5 h-5 text-slate-950" />
              </div>
              <div>
                <span className={`font-bold text-sm tracking-tight block ${isDark ? "text-white" : "text-slate-900"}`}>
                  BioResearch AI
                </span>
                <span className={`text-[10px] font-mono ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                  Autonomous Studio
                </span>
              </div>
            </button>

            <button 
              onClick={onBackToLanding}
              className={`p-1.5 rounded-lg transition-colors ${
                isDark ? "text-slate-500 hover:text-slate-300 hover:bg-white/5" : "text-slate-400 hover:text-slate-700 hover:bg-slate-100"
              }`}
              title="Back to Landing Page"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
          </div>

          {/* New Thread Button */}
          <button
            onClick={() => setQueryInput("")}
            className={`w-full py-2 px-3 rounded-lg border text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer ${
              isDark 
                ? "bg-blue-600/15 hover:bg-blue-600/25 border-blue-500/30 text-blue-400" 
                : "bg-blue-50 hover:bg-blue-100 border-blue-200 text-blue-700 font-bold"
            }`}
          >
            <Plus className="w-4 h-4" />
            <span>New Thread</span>
          </button>

          {/* Main Navigation */}
          <nav className="space-y-1 text-xs">
            <button className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg font-medium cursor-pointer ${
              isDark ? "bg-white/5 text-white" : "bg-slate-100 text-slate-900"
            }`}>
              <Home className="w-4 h-4 text-cyan-500" />
              <span>Home</span>
            </button>
            <button 
              onClick={() => handleChipClick("My Library: Saved small molecule candidates and dossiers")}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg transition-colors cursor-pointer ${
                isDark ? "text-slate-400 hover:text-white hover:bg-white/5" : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
              }`}
            >
              <BookMarked className="w-4 h-4" />
              <span>My Library</span>
            </button>
            <button 
              onClick={() => handleChipClick("History of recent autonomous drug discovery sessions")}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg transition-colors cursor-pointer ${
                isDark ? "text-slate-400 hover:text-white hover:bg-white/5" : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
              }`}
            >
              <History className="w-4 h-4" />
              <span>History</span>
            </button>
          </nav>

          {/* Recents */}
          <div className="pt-2">
            <span className={`text-[10px] font-semibold uppercase tracking-wider px-3 block mb-1 ${
              isDark ? "text-slate-500" : "text-slate-400"
            }`}>
              Recents
            </span>
            <div className="space-y-0.5">
              {RECENT_CHATS.map((title, idx) => (
                <button
                  key={idx}
                  onClick={() => handleChipClick(title)}
                  className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-colors text-left truncate cursor-pointer ${
                    isDark 
                      ? "text-slate-400 hover:text-slate-200 hover:bg-white/5" 
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                  }`}
                >
                  <MessageSquare className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span className="truncate">{title}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Tools */}
          <div className="pt-2">
            <span className={`text-[10px] font-semibold uppercase tracking-wider px-3 block mb-1 ${
              isDark ? "text-slate-500" : "text-slate-400"
            }`}>
              Tools
            </span>
            <div className="space-y-0.5 text-xs">
              <button 
                onClick={() => handleChipClick("Search top 20 papers on covalent EGFR inhibitors across PubMed and bioRxiv")}
                className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors text-left cursor-pointer ${
                  isDark ? "text-slate-400 hover:text-slate-200 hover:bg-white/5" : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <Search className="w-3.5 h-3.5 text-slate-400" />
                <span>Paper search</span>
              </button>
              <button 
                onClick={() => handleChipClick("Generate citation graph for kinase resistance papers")}
                className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors text-left cursor-pointer ${
                  isDark ? "text-slate-400 hover:text-slate-200 hover:bg-white/5" : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <Network className="w-3.5 h-3.5 text-slate-400" />
                <span>Citation Graph</span>
              </button>
            </div>
          </div>
        </div>

        {/* Bottom User & Settings Area */}
        <div className={`p-4 border-t space-y-3 ${isDark ? "border-white/5" : "border-slate-100"}`}>
          <div className={`space-y-1 text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}>
            <button 
              onClick={onOpenApiKeys}
              className={`w-full flex items-center justify-between px-2 py-1 rounded transition-colors cursor-pointer ${
                isDark ? "hover:text-white hover:bg-white/5" : "hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              <span className="flex items-center gap-1.5">
                <Key className="w-3 h-3 text-amber-500" />
                API & MCP Keys
              </span>
              <ExternalLink className="w-3 h-3 text-slate-400" />
            </button>
          </div>

          {/* User Profile Card */}
          <div className={`pt-2 border-t flex items-center justify-between ${
            isDark ? "border-white/5" : "border-slate-100"
          }`}>
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-white">
                M
              </div>
              <span className={`text-xs font-medium ${isDark ? "text-slate-200" : "text-slate-800"}`}>Mohammed</span>
            </div>
            
            {onToggleTheme && (
              <ThemeToggle theme={theme} onToggle={onToggleTheme} />
            )}
          </div>
        </div>
      </aside>

      {/* ============================================================ */}
      {/* 2. MAIN CENTER HERO SEARCH                                   */}
      {/* ============================================================ */}
      <main className="flex-1 flex flex-col justify-between p-6 sm:p-12 relative overflow-y-auto">
        
        {/* Subtle background glow */}
        <div className={`absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 rounded-full blur-3xl pointer-events-none ${
          isDark ? "bg-cyan-600/10" : "bg-blue-400/10"
        }`} />

        <div className="flex justify-end">
          {onToggleTheme && (
            <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          )}
        </div>

        {/* Central Search Area */}
        <div className="max-w-2xl w-full mx-auto text-center space-y-6">
          
          {/* Logo & Headline */}
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-cyan-400 to-blue-600 flex items-center justify-center text-slate-950 shadow-xl shadow-cyan-500/20 mb-4">
              <Atom className="w-7 h-7 text-slate-950" />
            </div>

            <div className="flex items-center gap-2">
              <h1 className={`text-2xl sm:text-3xl font-bold tracking-tight ${
                isDark ? "text-white" : "text-slate-900"
              }`}>
                BioResearch AI
              </h1>
            </div>

            <h2 className={`text-xl sm:text-2xl font-semibold mt-1 ${
              isDark ? "text-slate-300" : "text-slate-700"
            }`}>
              Research starts here
            </h2>
          </div>

          {/* Big Search Input Card */}
          <div className="space-y-3">
            <form 
              onSubmit={handleSubmit}
              className={`relative rounded-2xl p-2 shadow-2xl border transition-all text-left ${
                isDark 
                  ? "bg-[#1E2026] border-white/10 focus-within:border-blue-500/50" 
                  : "bg-white border-slate-200 focus-within:border-blue-500 shadow-slate-200/80"
              }`}
            >
              {/* Top Text Input */}
              <input
                type="text"
                value={queryInput}
                onChange={(e) => setQueryInput(e.target.value)}
                placeholder="Ask the research (e.g. Find novel small molecules for EGFR, KRAS G12D...)"
                className={`w-full bg-transparent px-4 py-3 text-base sm:text-lg outline-none ${
                  isDark ? "text-slate-100 placeholder:text-slate-500" : "text-slate-900 placeholder:text-slate-400"
                }`}
                autoFocus
              />

              {/* Bottom Controls Bar */}
              <div className={`flex items-center justify-between pt-2 px-2 border-t ${
                isDark ? "border-white/5" : "border-slate-100"
              }`}>
                
                {/* Left Controls */}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setQueryInput("Find novel small molecules related to EGFR target and explain why each candidate is worth investigating.")}
                    className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm transition-colors cursor-pointer ${
                      isDark ? "bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white" : "bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-900"
                    }`}
                    title="Insert benchmark prompt"
                  >
                    <Plus className="w-4 h-4" />
                  </button>

                  {/* Skills Dropdown */}
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setShowSkillDropdown(!showSkillDropdown)}
                      className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs transition-colors cursor-pointer ${
                        isDark ? "bg-white/5 hover:bg-white/10 text-slate-300" : "bg-slate-100 hover:bg-slate-200 text-slate-700"
                      }`}
                    >
                      <span>Skills</span>
                      <ChevronDown className="w-3 h-3 text-slate-400" />
                    </button>

                    {showSkillDropdown && (
                      <div className={`absolute left-0 bottom-full mb-2 w-52 rounded-xl shadow-xl p-1 z-30 space-y-0.5 text-xs border ${
                        isDark ? "bg-[#18191E] border-white/10" : "bg-white border-slate-200"
                      }`}>
                        {[
                          "Target-to-Molecule",
                          "Literature Extraction",
                          "Lipinski Ro5 & ADMET",
                          "In Silico Docking",
                          "Covalent Warhead Screening"
                        ].map((skill, i) => (
                          <button
                            key={i}
                            type="button"
                            onClick={() => {
                              setSelectedSkill(skill);
                              setShowSkillDropdown(false);
                            }}
                            className={`w-full text-left px-2.5 py-1.5 rounded-lg transition-colors ${
                              isDark ? "text-slate-300 hover:bg-white/10 hover:text-white" : "text-slate-700 hover:bg-slate-100 hover:text-slate-900"
                            }`}
                          >
                            {skill}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Deep Mode Pill */}
                  <button
                    type="button"
                    onClick={() => setIsDeepMode(!isDeepMode)}
                    className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors cursor-pointer ${
                      isDeepMode 
                        ? "bg-blue-600/20 border-blue-500/40 text-blue-600 dark:text-blue-300 font-semibold" 
                        : isDark
                        ? "bg-white/5 border-white/10 text-slate-400"
                        : "bg-slate-100 border-slate-200 text-slate-600"
                    }`}
                  >
                    <Sparkles className="w-3 h-3 text-blue-500" />
                    <span>Deep +</span>
                  </button>
                </div>

                {/* Right Controls */}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={toggleVoice}
                    className={`w-7 h-7 rounded-lg flex items-center justify-center transition-colors cursor-pointer ${
                      isListeningVoice 
                        ? "bg-red-500/20 text-red-500 animate-pulse border border-red-500/40" 
                        : isDark
                        ? "text-slate-400 hover:text-white hover:bg-white/5"
                        : "text-slate-500 hover:text-slate-900 hover:bg-slate-100"
                    }`}
                    title={isListeningVoice ? "Listening to voice input..." : "Voice input"}
                  >
                    <Mic className="w-3.5 h-3.5" />
                  </button>

                  <button
                    type="submit"
                    className="w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center shadow-lg shadow-blue-600/30 transition-all cursor-pointer"
                    title="Launch Autonomous Research"
                  >
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </form>

            {/* LIVE TARGET IDENTIFICATION & BIO-NER INTELLIGENCE WHILE TYPING */}
            {liveTargetDetection && (
              <div 
                onClick={() => handleSubmit()}
                className={`p-3 rounded-xl border backdrop-blur-md text-left transition-all cursor-pointer hover:border-blue-500 ${liveTargetDetection.badgeBg}`}
              >
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className={`font-bold flex items-center gap-1.5 ${liveTargetDetection.color}`}>
                    <Activity className="w-3.5 h-3.5 animate-pulse" />
                    <span>Live Researching Intelligence: {liveTargetDetection.target}</span>
                  </span>
                  <span className={`text-[10px] font-mono ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    Press Enter to Launch →
                  </span>
                </div>
                <div className={`flex flex-wrap items-center gap-3 text-[11px] ${isDark ? "text-slate-300" : "text-slate-700"}`}>
                  <span>Modality: <b className={isDark ? "text-white" : "text-slate-900"}>{liveTargetDetection.modality}</b></span>
                  <span>PubMed: <b className="text-emerald-500 font-semibold">{liveTargetDetection.pubmedHits}</b></span>
                  <span>ChEMBL: <b className="text-blue-500 font-semibold">{liveTargetDetection.chemblCompounds}</b></span>
                </div>
              </div>
            )}
          </div>

          {/* Quick Action Suggestion Chips */}
          <div className="flex flex-wrap items-center justify-center gap-2.5 pt-2">
            {PRESET_QUERIES.map((item, idx) => (
              <button
                key={idx}
                onClick={() => handleChipClick(item.query)}
                className={`px-3.5 py-1.5 rounded-xl border text-xs font-medium transition-all shadow-xs flex items-center gap-1.5 cursor-pointer ${
                  isDark 
                    ? "bg-[#1E2026] hover:bg-[#262830] border-white/5 hover:border-white/15 text-slate-300" 
                    : "bg-white hover:bg-slate-50 border-slate-200 text-slate-700 hover:text-slate-900 shadow-slate-200/50"
                }`}
              >
                {idx === 0 && <Sparkles className="w-3 h-3 text-cyan-500" />}
                {idx === 1 && <FlaskConical className="w-3 h-3 text-emerald-500" />}
                {idx === 2 && <FileText className="w-3 h-3 text-purple-500" />}
                {idx === 3 && <Atom className="w-3 h-3 text-blue-500" />}
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Footer Tagline */}
        <div className={`text-center text-xs pb-2 ${isDark ? "text-slate-500" : "text-slate-400"}`}>
          The new standard for academic & drug research
        </div>
      </main>
    </div>
  );
}
