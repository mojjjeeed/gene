"use client";

import React, { useState, useEffect } from "react";
import { 
  ArrowRight, 
  Play, 
  Sparkles, 
  Search, 
  Atom, 
  ChevronRight, 
  ShieldCheck,
  Zap
} from "lucide-react";
import ChemicalStructureViewer from "./ChemicalStructureViewer";
import ThemeToggle from "./ThemeToggle";

interface LandingHeroPageProps {
  onStartDiscovering: () => void;
  onLaunchDemo: (query?: string) => void;
  onOpenApiKeys: () => void;
  theme?: "light" | "dark";
  onToggleTheme?: () => void;
}

const ROLLING_WORDS = [
  "Mapped.",
  "Agentized.",
  "Autonomized.",
  "Synthesized.",
  "Accelerated.",
  "Validated.",
  "Decoded."
];

export default function LandingHeroPage({
  onStartDiscovering,
  onLaunchDemo,
  onOpenApiKeys,
  theme = "light",
  onToggleTheme
}: LandingHeroPageProps) {
  const [wordIndex, setWordIndex] = useState(0);
  const [isFlipping, setIsFlipping] = useState(false);

  const isDark = theme === "dark";

  // Smooth rolling word cycle
  useEffect(() => {
    const interval = setInterval(() => {
      setIsFlipping(true);
      setTimeout(() => {
        setWordIndex((prev) => (prev + 1) % ROLLING_WORDS.length);
        setIsFlipping(false);
      }, 300);
    }, 2400);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className={`relative min-h-screen overflow-x-hidden selection:bg-blue-600 selection:text-white transition-colors duration-200 ${
      isDark ? "bg-[#0E1015] text-slate-100" : "bg-[#FAFAFC] text-slate-900"
    }`}>
      
      {/* 1. TOP ANNOUNCEMENT BANNER */}
      <div className={`w-full py-2 px-4 text-center text-xs sm:text-[13px] font-medium border-b flex items-center justify-center gap-2 ${
        isDark ? "bg-[#16181F] border-white/5 text-slate-300" : "bg-[#F3F4F6] border-slate-200/80 text-slate-700"
      }`}>
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-red-500 text-white animate-pulse">
          <span className="w-1.5 h-1.5 rounded-full bg-white"></span>
          LIVE
        </span>
        <span className={isDark ? "text-slate-200 font-semibold" : "text-slate-800 font-semibold"}>
          Agentic Drug Discovery is live
        </span>
        <button 
          onClick={onStartDiscovering}
          className="text-blue-500 hover:text-blue-600 font-medium inline-flex items-center gap-1 hover:underline ml-1 cursor-pointer"
        >
          Explore the research engine →
        </button>
      </div>

      {/* 2. NAVIGATION BAR */}
      <nav className={`sticky top-0 z-40 backdrop-blur-md border-b px-6 py-4 transition-colors ${
        isDark ? "bg-[#0E1015]/90 border-white/10" : "bg-white/90 border-slate-200/80"
      }`}>
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          
          {/* Logo & Beta Pill */}
          <div className="flex items-center gap-3">
            <button 
              onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
              className="flex items-center gap-2 group cursor-pointer text-left"
            >
              <div className={`w-7 h-7 rounded-full border-2 flex items-center justify-center transition-transform group-hover:scale-105 ${
                isDark ? "border-slate-300" : "border-slate-800"
              }`}>
                <div className={`w-2.5 h-2.5 rounded-full ${isDark ? "bg-white" : "bg-slate-900"}`}></div>
              </div>
              <span className={`font-bold text-xl tracking-tight ${isDark ? "text-white" : "text-slate-900"}`}>
                BioResearch AI
              </span>
              <span className={`text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded border ${
                isDark ? "bg-white/10 text-slate-300 border-white/10" : "bg-slate-100 text-slate-600 border-slate-300"
              }`}>
                BETA
              </span>
            </button>

            {/* Nav Menu Links */}
            <div className={`hidden lg:flex items-center gap-6 ml-8 text-sm font-medium ${
              isDark ? "text-slate-400" : "text-slate-600"
            }`}>
              <button onClick={onStartDiscovering} className="hover:text-blue-500 transition-colors cursor-pointer">Lab</button>
              <button onClick={onStartDiscovering} className="hover:text-blue-500 transition-colors cursor-pointer">Research</button>
              <button onClick={() => onLaunchDemo("EGFR Kinase Inhibitor Scaffolds")} className="hover:text-blue-500 transition-colors cursor-pointer">Molecules</button>
              <button onClick={onStartDiscovering} className="hover:text-blue-500 transition-colors cursor-pointer">Papers</button>
              <button onClick={onStartDiscovering} className="hover:text-blue-500 transition-colors cursor-pointer">Discovery</button>
              <button onClick={onStartDiscovering} className="hover:text-blue-500 transition-colors cursor-pointer">Agents</button>
            </div>
          </div>

          {/* Right Nav Buttons */}
          <div className="flex items-center gap-3">
            {onToggleTheme && (
              <ThemeToggle theme={theme} onToggle={onToggleTheme} />
            )}

            <button
              onClick={onOpenApiKeys}
              className={`hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors cursor-pointer ${
                isDark 
                  ? "bg-white/5 hover:bg-white/10 text-slate-200 border-white/10" 
                  : "bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-200"
              }`}
            >
              <Zap className="w-3.5 h-3.5 text-amber-500" />
              <span>AI Keys</span>
            </button>

            <button 
              onClick={onStartDiscovering}
              className={`hidden md:flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-colors cursor-pointer ${
                isDark 
                  ? "bg-white/5 hover:bg-white/10 text-slate-200 border-white/10" 
                  : "bg-slate-100 hover:bg-slate-200 text-slate-800 border-slate-200"
              }`}
            >
              <span>New in September</span>
              <Search className="w-3.5 h-3.5 text-slate-400" />
            </button>

            <button 
              onClick={onStartDiscovering}
              className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-colors cursor-pointer ${
                isDark ? "text-slate-300 hover:text-white hover:bg-white/5" : "text-slate-700 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              Sign in
            </button>
          </div>
        </div>
      </nav>

      {/* 3. HERO SECTION WITH FLOATING SCIENTIFIC CARDS */}
      <section className="relative max-w-7xl mx-auto px-4 sm:px-6 pt-12 pb-20 sm:pt-20 sm:pb-32 overflow-visible">
        
        {/* Subtle grid background */}
        <div 
          className="absolute inset-0 pointer-events-none opacity-40"
          style={{
            backgroundImage: `radial-gradient(${isDark ? "#475569" : "#CBD5E1"} 1px, transparent 1px)`,
            backgroundSize: `24px 24px`,
            maskImage: `radial-gradient(ellipse 60% 50% at 50% 40%, black 70%, transparent 100%)`
          }}
        />

        {/* FLOATING CARD 1: TOP-LEFT (RESEARCH NOTE · 021 | NATURE) */}
        <div 
          className={`hidden xl:block absolute left-2 top-10 w-64 p-4 rounded-xl shadow-xl transition-all duration-300 hover:scale-105 hover:z-20 cursor-pointer border ${
            isDark 
              ? "bg-[#18191E] border-white/10 shadow-black/50" 
              : "bg-white border-slate-200/90 shadow-slate-200/70"
          }`}
          style={{ transform: "rotate(-6deg)" }}
          onClick={() => onLaunchDemo("Machine Learning in Protein Design")}
        >
          <div className="flex items-center justify-between text-[10px] font-mono font-semibold tracking-wider text-slate-400 mb-2">
            <span>RESEARCH NOTE · 021</span>
          </div>
          <div className="inline-block px-2 py-0.5 rounded text-[10px] font-bold text-white bg-[#991b1b] mb-2 uppercase tracking-wide">
            NATURE
          </div>
          <h4 className={`font-bold text-sm leading-snug mb-1 ${isDark ? "text-white" : "text-slate-900"}`}>
            Machine Learning in Protein Design
          </h4>
          <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-2">
            Target-conditioned generative diffusion models for macromolecular backbone and de novo binder design.
          </p>
        </div>

        {/* FLOATING CARD 2: MIDDLE-LEFT (DRUG DESIGN · 032 | ACS + 2D MOLECULE) */}
        <div 
          className={`hidden lg:block absolute left-4 top-64 w-72 p-4 rounded-xl shadow-2xl transition-all duration-300 hover:scale-105 hover:z-20 cursor-pointer border ${
            isDark 
              ? "bg-[#18191E] border-white/10 shadow-black/50" 
              : "bg-white border-slate-200/90 shadow-slate-200/80"
          }`}
          style={{ transform: "rotate(-2deg)" }}
          onClick={() => onLaunchDemo("EGFR Kinase Inhibitor Generative Design")}
        >
          <div className="flex items-center justify-between text-[10px] font-mono font-semibold tracking-wider text-slate-400 mb-2">
            <span>DRUG DESIGN · 032</span>
          </div>
          <div className="inline-block px-2 py-0.5 rounded text-[10px] font-bold text-white bg-[#1e3a8a] mb-2 uppercase tracking-wide">
            ACS
          </div>
          <h4 className={`font-bold text-sm leading-snug mb-1 ${isDark ? "text-white" : "text-slate-900"}`}>
            Generative AI-Based Drug Design
          </h4>
          <p className="text-[11px] text-slate-400 leading-relaxed mb-3">
            Target-aware molecular generation for EGFR inhibitors with docking validation.
          </p>
          <div className={`p-2 rounded-lg border ${
            isDark ? "bg-[#121316] border-white/5" : "bg-slate-50 border-slate-100"
          }`}>
            <ChemicalStructureViewer 
              moleculeName="Candidate A-17" 
              isCompact={true} 
              theme={theme} 
            />
          </div>
        </div>

        {/* FLOATING CARD 3: BOTTOM-LEFT (QSAR · 028 | NATURE REVIEWS) */}
        <div 
          className={`hidden xl:block absolute left-12 bottom-6 w-64 p-4 rounded-xl shadow-xl transition-all duration-300 hover:scale-105 hover:z-20 cursor-pointer border ${
            isDark 
              ? "bg-[#18191E] border-white/10 shadow-black/50" 
              : "bg-white border-slate-200/90 shadow-slate-200/70"
          }`}
          style={{ transform: "rotate(3deg)" }}
          onClick={() => onLaunchDemo("Integrating QSAR and Deep Learning in Drug Discovery")}
        >
          <div className="flex items-center justify-between text-[10px] font-mono font-semibold tracking-wider text-slate-400 mb-2">
            <span>QSAR · 028</span>
          </div>
          <div className="inline-block px-2 py-0.5 rounded text-[10px] font-bold text-white bg-[#9a3412] mb-2 uppercase tracking-wide">
            NATURE REVIEWS
          </div>
          <h4 className={`font-bold text-sm leading-snug mb-1 ${isDark ? "text-white" : "text-slate-900"}`}>
            Integrating QSAR and Deep Learning in Drug Discovery
          </h4>
          <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-2">
            The emergence of deep QSAR for pharmaceutical property estimation and cellular toxicity profiling.
          </p>
        </div>

        {/* FLOATING CARD 4: TOP-RIGHT (READING NOTE · 047 | NPJ DRUG DISCOVERY) */}
        <div 
          className={`hidden xl:block absolute right-4 top-14 w-64 p-4 rounded-xl shadow-xl transition-all duration-300 hover:scale-105 hover:z-20 cursor-pointer border ${
            isDark 
              ? "bg-[#18191E] border-white/10 shadow-black/50" 
              : "bg-white border-slate-200/90 shadow-slate-200/70"
          }`}
          style={{ transform: "rotate(4deg)" }}
          onClick={() => onLaunchDemo("AI Meets Physics in Structure-Based Drug Discovery")}
        >
          <div className="flex items-center justify-between text-[10px] font-mono font-semibold tracking-wider text-slate-400 mb-2">
            <span>READING NOTE · 047</span>
          </div>
          <div className="inline-block px-2 py-0.5 rounded text-[10px] font-bold text-white bg-[#14532d] mb-2 uppercase tracking-wide">
            NPJ DRUG DISCOVERY
          </div>
          <h4 className={`font-bold text-sm leading-snug mb-1 ${isDark ? "text-white" : "text-slate-900"}`}>
            AI Meets Physics in Structure-Based Drug Discovery
          </h4>
          <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-2">
            Computational structure-based discovery for GPCR targets with quantum mechanical scoring.
          </p>
        </div>

        {/* FLOATING CARD 5: MIDDLE-RIGHT CAPSULE (Research Checkpoint + Equalizer) */}
        <div className="hidden lg:flex absolute right-6 top-72 items-center gap-3 bg-[#18191E] text-white px-4 py-2.5 rounded-2xl shadow-2xl border border-white/10 z-10 transition-transform hover:scale-105">
          <span className="text-xs font-semibold text-slate-300">Research checkpoint</span>
          
          {/* Animated Equalizer Waveform */}
          <div className="flex items-center gap-0.5 h-5 px-1">
            <span className="w-1 bg-white rounded-full animate-eq-1"></span>
            <span className="w-1 bg-white rounded-full animate-eq-2"></span>
            <span className="w-1 bg-white rounded-full animate-eq-3"></span>
            <span className="w-1 bg-white rounded-full animate-eq-4"></span>
            <span className="w-1 bg-white rounded-full animate-eq-5"></span>
          </div>

          <span className="text-xs font-mono font-bold text-white">18 / 25 min</span>
        </div>

        {/* FLOATING CARD 6: BOTTOM-RIGHT (DISCOVERY REVIEW · 014 | NATURE) */}
        <div 
          className={`hidden xl:block absolute right-8 bottom-4 w-64 p-4 rounded-xl shadow-xl transition-all duration-300 hover:scale-105 hover:z-20 cursor-pointer border ${
            isDark 
              ? "bg-[#18191E] border-white/10 shadow-black/50" 
              : "bg-white border-slate-200/90 shadow-slate-200/70"
          }`}
          style={{ transform: "rotate(-3deg)" }}
          onClick={() => onLaunchDemo("Natural Product Drug Discovery via AI")}
        >
          <div className="flex items-center justify-between text-[10px] font-mono font-semibold tracking-wider text-slate-400 mb-2">
            <span>DISCOVERY REVIEW · 014</span>
          </div>
          <div className="inline-block px-2 py-0.5 rounded text-[10px] font-bold text-white bg-[#581c87] mb-2 uppercase tracking-wide">
            NATURE
          </div>
          <h4 className={`font-bold text-sm leading-snug mb-1 ${isDark ? "text-white" : "text-slate-900"}`}>
            Artificial Intelligence for Natural Product Drug Discovery
          </h4>
          <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-2">
            AI-assisted exploration of natural-product chemical space and novel biosynthetic gene clusters.
          </p>
        </div>


        {/* ============================================================ */}
        {/* CENTER HERO TEXT & ROLLING WORD HEADLINE                     */}
        {/* ============================================================ */}
        <div className="relative z-10 max-w-3xl mx-auto text-center">
          
          {/* Central Live Badge */}
          <div className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold mb-8 shadow-sm border ${
            isDark 
              ? "bg-blue-950/40 border-blue-500/30 text-blue-300" 
              : "bg-blue-50 border-blue-200 text-blue-700"
          }`}>
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
            <span className="font-bold text-red-500">LIVE</span>
            <span>Agentic Drug Discovery is live</span>
            <button 
              onClick={onStartDiscovering}
              className="text-blue-500 hover:text-blue-600 font-semibold flex items-center gap-0.5 ml-1 cursor-pointer"
            >
              New research engine →
            </button>
          </div>

          {/* MAIN HEADLINE WITH ROLLING TEXT */}
          <h1 className={`text-4xl sm:text-6xl md:text-7xl font-extrabold tracking-tight leading-[1.08] mb-6 ${
            isDark ? "text-white" : "text-slate-900"
          }`}>
            Everything an <br />
            <span className="bg-gradient-to-r from-[#FF5A36] via-[#A855F7] to-[#6366F1] bg-clip-text text-transparent">
              AI Drug Discovery
            </span> <br />
            <span className="bg-gradient-to-r from-[#8B5CF6] to-[#4F46E5] bg-clip-text text-transparent">
              Researcher
            </span> <br />
            <span>needs. </span>
            
            {/* The Rolling Word Element */}
            <span className="relative inline-block overflow-hidden align-bottom">
              <span 
                className={`inline-block font-extrabold transition-all duration-300 ${
                  isFlipping 
                    ? "opacity-0 -translate-y-4 blur-[2px]" 
                    : "opacity-100 translate-y-0 blur-0"
                } ${isDark ? "text-white" : "text-slate-950"}`}
              >
                {ROLLING_WORDS[wordIndex]}
              </span>
            </span>
          </h1>

          {/* Subtitle */}
          <p className={`text-base sm:text-lg max-w-2xl mx-auto leading-relaxed mb-10 ${
            isDark ? "text-slate-300" : "text-slate-600"
          }`}>
            Discover drug candidates, inspect molecules, trace the literature, and connect <b className={isDark ? "text-white" : "text-slate-900"}>targets</b>, <b className={isDark ? "text-white" : "text-slate-900"}>compounds</b>, <b className={isDark ? "text-white" : "text-slate-900"}>mechanisms</b> and <b className={isDark ? "text-white" : "text-slate-900"}>evidence</b> through an agentic research workflow.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={onStartDiscovering}
              className={`w-full sm:w-auto px-8 py-3.5 rounded-xl font-semibold text-sm sm:text-base shadow-xl transition-all flex items-center justify-center gap-2 group cursor-pointer ${
                isDark 
                  ? "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-600/30" 
                  : "bg-slate-950 hover:bg-slate-800 text-white shadow-slate-950/20"
              }`}
            >
              <span>Start discovering free</span>
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </button>

            <button
              onClick={() => onLaunchDemo("Find novel small molecules related to EGFR target and explain why each candidate is worth investigating.")}
              className={`w-full sm:w-auto px-7 py-3.5 rounded-xl font-semibold text-sm sm:text-base border shadow-sm transition-all flex items-center justify-center gap-2 cursor-pointer ${
                isDark 
                  ? "bg-white/5 hover:bg-white/10 text-white border-white/15" 
                  : "bg-white hover:bg-slate-50 text-slate-800 border-slate-300"
              }`}
            >
              <div className={`w-5 h-5 rounded-full flex items-center justify-center ${
                isDark ? "bg-white/10 text-white" : "bg-slate-100 text-slate-700"
              }`}>
                <Play className={`w-3 h-3 ml-0.5 ${isDark ? "fill-white" : "fill-slate-700"}`} />
              </div>
              <span>See research demo</span>
            </button>
          </div>

          {/* Micro trust stats */}
          <div className={`mt-12 pt-8 border-t flex flex-wrap items-center justify-center gap-6 sm:gap-12 text-xs font-medium ${
            isDark ? "border-white/10 text-slate-400" : "border-slate-200/60 text-slate-500"
          }`}>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span><b>PubMed & ChEMBL</b> Real-time APIs</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Atom className="w-3.5 h-3.5 text-blue-500" />
              <span><b>RDKit 2D/3D</b> Deterministic Cheminformatics</span>
            </div>
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-purple-500" />
              <span><b>Lipinski Ro5 & ADMET</b> Auto-Scoring</span>
            </div>
          </div>
        </div>
      </section>

      {/* 4. BENCHMARK RESEARCH STUDIES SECTION */}
      <section className={`border-t py-16 px-6 ${
        isDark ? "bg-[#121316] border-white/10" : "bg-slate-100/70 border-slate-200"
      }`}>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-10">
            <span className="text-xs font-mono uppercase tracking-wider text-blue-600 font-bold">
              ✦ Pre-Indexed Autonomous Pipelines
            </span>
            <h2 className={`text-2xl sm:text-3xl font-bold mt-1 ${isDark ? "text-white" : "text-slate-900"}`}>
              Explore High-Value Therapeutic Targets
            </h2>
            <p className={`text-sm max-w-xl mx-auto mt-2 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
              Launch our autonomous discovery agents against real oncological, neurological, and metabolic targets with instant literature grounded briefings.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              {
                target: "EGFR T790M / C797S",
                disease: "Non-Small Cell Lung Cancer",
                lead: "Candidate A-17 (4th Gen)",
                score: "-9.4 kcal/mol",
                query: "Find novel small molecules related to EGFR T790M C797S resistance and explain why each candidate is worth investigating."
              },
              {
                target: "KRAS G12D Switch-II",
                disease: "Pancreatic Ductal Adenocarcinoma",
                lead: "Candidate B-04 (Allosteric)",
                score: "-8.8 kcal/mol",
                query: "Discover novel allosteric pocket inhibitors targeting KRAS G12D with optimal ADMET profiles."
              },
              {
                target: "BACE1 & Amyloid Beta",
                disease: "Alzheimer's Disease",
                lead: "Candidate C-22 (Macrocycle)",
                score: "-10.1 kcal/mol",
                query: "Investigate dual BACE1 and tau aggregation inhibitors with blood-brain barrier permeability."
              },
              {
                target: "CDK4/6 Cyclin-D Pocket",
                disease: "Metastatic Breast Cancer",
                lead: "Candidate D-09 (Covalent)",
                score: "-9.8 kcal/mol",
                query: "Synthesize novel CDK4/6 selective inhibitors overcoming palbociclib acquired resistance."
              }
            ].map((item, idx) => (
              <div 
                key={idx}
                onClick={() => onLaunchDemo(item.query)}
                className={`p-5 rounded-xl border shadow-sm hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between ${
                  isDark 
                    ? "bg-[#18191E] border-white/10 hover:border-blue-500/50" 
                    : "bg-white border-slate-200/80 hover:border-blue-500/40"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 mb-2">
                    <span>TARGET {idx + 1}</span>
                    <span className="text-emerald-500 font-bold">{item.score}</span>
                  </div>
                  <h3 className={`font-bold text-sm transition-colors ${
                    isDark ? "text-white group-hover:text-blue-400" : "text-slate-900 group-hover:text-blue-600"
                  }`}>
                    {item.target}
                  </h3>
                  <p className="text-xs text-slate-400 mt-1 mb-3">
                    {item.disease}
                  </p>
                </div>

                <div className={`pt-3 border-t flex items-center justify-between text-xs ${
                  isDark ? "border-white/5" : "border-slate-100"
                }`}>
                  <span className="text-slate-400 font-medium text-[11px] truncate">{item.lead}</span>
                  <ChevronRight className="w-4 h-4 text-slate-400 group-hover:translate-x-1 group-hover:text-blue-500 transition-all" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className={`border-t py-8 px-6 text-center text-xs ${
        isDark ? "bg-[#0E1015] border-white/10 text-slate-500" : "bg-white border-slate-200 text-slate-500"
      }`}>
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${
              isDark ? "border-slate-400" : "border-slate-800"
            }`}>
              <div className={`w-1.5 h-1.5 rounded-full ${isDark ? "bg-white" : "bg-slate-900"}`}></div>
            </div>
            <span className={`font-bold ${isDark ? "text-white" : "text-slate-900"}`}>BioResearch AI</span>
            <span>— Autonomous Biomedical Discovery</span>
          </div>
          <div>
            Built with Next.js, LangGraph Multi-Agent Workflows & Deterministic Cheminformatics
          </div>
        </div>
      </footer>
    </div>
  );
}
