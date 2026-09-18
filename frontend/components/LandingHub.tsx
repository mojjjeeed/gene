"use client";

import React, { useState } from "react";
import { Search, Sparkles, BookOpen, ArrowRight, ShieldCheck, Activity, Dna, Brain } from "lucide-react";

interface LandingHubProps {
  onLaunchStudy: (query: string) => void;
  isLoading: boolean;
}

const BENCHMARK_STUDIES = [
  {
    id: "anger",
    title: "Neurobiology of Anger Management & Impulsive Aggression",
    category: "Behavioral Neuroscience & CNS",
    description: "Multi-agent literature synthesis exploring prefrontal-amygdala circuitry, central 5-HT1A autoreceptors, and autonomic beta-blockade.",
    icon: "🧠",
    sources: 18,
    lead: "Propranolol CNS Derivative",
    query: "anger management and neurobiology of aggression small molecule modulators",
    score: "8.9"
  },
  {
    id: "alzheimer",
    title: "Alzheimer's Disease: Dual BACE1 & Amyloid Aggregation Blockers",
    category: "Neurodegenerative Diseases",
    description: "Cross-referencing PubMed and ChEMBL for dual-target AChE/BACE1 inhibitors with high blood-brain barrier permeability.",
    icon: "🧬",
    sources: 24,
    lead: "Donepezil-BACE1 Hybrid",
    query: "Alzheimer's disease beta-amyloid & BACE1 small molecule inhibitors",
    score: "8.7"
  },
  {
    id: "kras",
    title: "KRAS G12D / G12C Allosteric Pocket Covalent Inhibitors",
    category: "Targeted Oncology",
    description: "Targeting the induced switch-II pocket of mutant KRAS oncoproteins in pancreatic ductal adenocarcinoma.",
    icon: "⚡",
    sources: 22,
    lead: "Sotorasib Switch-II Analog",
    query: "KRAS G12D allosteric inhibitors in pancreatic ductal adenocarcinoma",
    score: "9.1"
  },
  {
    id: "egfr",
    title: "EGFR T790M / C797S Resistance & PROTAC Degraders",
    category: "Kinase Inhibitors",
    description: "Overcoming Osimertinib triple-mutation resistance via targeted proteasomal degradation (PROTACs).",
    icon: "🛡️",
    sources: 16,
    lead: "Osimertinib-PROTAC Degrader",
    query: "Targeted covalent inhibitors for EGFR T790M / C797S resistance",
    score: "8.6"
  }
];

export default function LandingHub({ onLaunchStudy, isLoading }: LandingHubProps) {
  const [searchInput, setSearchInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchInput.trim()) {
      onLaunchStudy(searchInput.trim());
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      {/* Hero Section */}
      <div className="text-center mb-12">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#0014AA]/40 border border-[#BEF5DC]/30 text-xs font-semibold uppercase tracking-widest text-[#BEF5DC] mb-6">
          <Sparkles className="w-3.5 h-3.5 text-[#00D084]" />
          Autonomous Biomedical Research Acceleration
        </div>

        <h1 className="font-serif text-4xl sm:text-6xl font-semibold tracking-tight text-white leading-[1.08] mb-6">
          Where Global Science Meets <br className="hidden sm:inline" />
          <span className="italic text-[#BEF5DC]">Chemical Precision</span>
        </h1>

        <p className="text-base sm:text-lg text-slate-300 max-w-2xl mx-auto leading-relaxed">
          Autonomous multi-agent intelligence across <b>PubMed, bioRxiv, arXiv, ChEMBL & PubChem</b> with deterministic <b>RDKit 3D chemical validation</b> and interactive <b>physiological bond inspection</b>.
        </p>
      </div>

      {/* Interactive Search Launcher */}
      <div className="max-w-3xl mx-auto mb-14">
        <form onSubmit={handleSubmit} className="relative">
          <div className="aha-glass-card p-2 flex items-center gap-3 shadow-2xl shadow-[#0037FF]/20">
            <Search className="w-6 h-6 text-[#BEF5DC] ml-3" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="e.g. anger management, KRAS G12D inhibitors, Alzheimer's BACE1..."
              className="flex-grow bg-transparent border-none outline-none text-white text-base sm:text-lg placeholder:text-slate-400 px-2 py-2"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading}
              className="bg-gradient-to-r from-[#0014AA] via-[#0037FF] to-[#00D084] hover:from-[#0037FF] hover:to-[#00D084] text-white font-semibold text-sm sm:text-base px-6 py-3 rounded-lg shadow-lg shadow-[#0037FF]/40 transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
            >
              {isLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Mining...</span>
                </>
              ) : (
                <>
                  <span>Start Studio</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* AHA Global Statistics Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-16">
        <div className="aha-glass-card p-5 text-center">
          <div className="font-serif text-3xl sm:text-4xl font-bold text-[#BEF5DC] mb-1">36M+</div>
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">PubMed & PMC Abstracts</div>
        </div>
        <div className="aha-glass-card p-5 text-center">
          <div className="font-serif text-3xl sm:text-4xl font-bold text-[#93C5FD] mb-1">2.4M</div>
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">ChEMBL Bioactivities</div>
        </div>
        <div className="aha-glass-card p-5 text-center">
          <div className="font-serif text-3xl sm:text-4xl font-bold text-emerald-400 mb-1">100%</div>
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">RDKit Physical Validation</div>
        </div>
        <div className="aha-glass-card p-5 text-center">
          <div className="font-serif text-3xl sm:text-4xl font-bold text-amber-300 mb-1">8.9/10</div>
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">DPO Critic Quality Gate</div>
        </div>
      </div>

      {/* Curated Benchmark Research Notebooks */}
      <div>
        <div className="flex items-center justify-between mb-6 pb-3 border-b border-[#BEF5DC]/20">
          <div>
            <h2 className="font-serif text-2xl font-semibold text-white">
              Featured Benchmark Research Studies
            </h2>
            <p className="text-xs text-slate-400 mt-1">Select any study to instantly load the full 3-Panel Studio</p>
          </div>
          <div className="text-xs font-mono uppercase tracking-widest text-[#BEF5DC]">
            ✦ Verified Datasets
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {BENCHMARK_STUDIES.map((study) => (
            <div
              key={study.id}
              className="aha-glass-card p-6 flex flex-col justify-between hover:border-[#BEF5DC] transition-all group"
            >
              <div>
                <div className="flex items-start justify-between mb-3">
                  <span className="text-3xl">{study.icon}</span>
                  <span className="text-xs font-mono font-bold bg-[#001852] border border-[#00D084]/40 text-[#BEF5DC] px-2.5 py-1 rounded-full">
                    DPO Score: {study.score}/10
                  </span>
                </div>

                <h3 className="font-serif text-xl font-semibold text-white group-hover:text-[#BEF5DC] transition-colors mb-2 leading-snug">
                  {study.title}
                </h3>

                <div className="text-xs font-bold text-[#BEF5DC] uppercase tracking-wider mb-3">
                  {study.category} • {study.sources} Indexed Sources
                </div>

                <p className="text-sm text-slate-300 leading-relaxed mb-4">
                  {study.description}
                </p>
              </div>

              <div className="pt-4 border-t border-white/10 flex items-center justify-between">
                <span className="text-xs font-mono bg-[#000D2E] border border-emerald-500/40 text-emerald-300 px-2.5 py-1 rounded">
                  💊 {study.lead}
                </span>

                <button
                  onClick={() => onLaunchStudy(study.query)}
                  disabled={isLoading}
                  className="text-xs font-bold text-[#BEF5DC] group-hover:text-white flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <span>Open Studio</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
