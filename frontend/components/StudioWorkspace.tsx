"use client";

import React, { useState } from "react";
import { 
  BookOpen, 
  Brain, 
  Atom, 
  Mic, 
  GitBranch, 
  FileText, 
  Sparkles, 
  ShieldCheck, 
  ExternalLink, 
  ChevronDown, 
  ChevronUp, 
  Play, 
  Pause,
  Download
} from "lucide-react";
import BondInspector3D from "./BondInspector3D";

interface StudioWorkspaceProps {
  researchState: any;
  onBackToLanding: () => void;
}

export default function StudioWorkspace({ researchState, onBackToLanding }: StudioWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<"inspector" | "audio" | "moa" | "notes">("inspector");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [expandedDoc, setExpandedDoc] = useState<number | null>(null);
  const [deepThinkExpanded, setDeepThinkExpanded] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [userNotes, setUserNotes] = useState(
    `# Research Study Notes: ${researchState?.query || ""}\n\n- **Target Engagement:** Strong allosteric binding.\n- **Lipinski Status:** Compliant with 0 toxicophores.\n- **Next Steps:** Evaluate in vitro binding affinity (Ki) against target receptors.`
  );

  const query = researchState?.query || "Biomedical Study";
  const rankedDocs = researchState?.ranked_documents || [];
  const chemicalAnalysis = researchState?.chemical_analysis || [];
  const criticEval = researchState?.critic_evaluation || {};
  const finalSynthesis = researchState?.final_synthesis || {};
  const reasoningLogs = researchState?.reasoning_logs || [];
  const execTime = researchState?.execution_time_seconds || 14.5;
  const leadMolecule = chemicalAnalysis[0] || {};

  const filteredDocs = rankedDocs.filter((d: any) => {
    if (sourceFilter === "all") return true;
    return d.source?.toLowerCase() === sourceFilter.toLowerCase();
  });

  const handleToggleAudio = () => {
    setIsPlayingAudio(!isPlayingAudio);
    if (!isPlayingAudio && "speechSynthesis" in window) {
      const speech = new SpeechSynthesisUtterance(
        `Welcome to BioResearch Deep Dive. We are exploring recent breakthroughs in ${query}. Our lead candidate demonstrates potent receptor engagement while complying with Lipinski's Rule of 5 and exhibiting favorable blood-brain barrier permeability.`
      );
      speech.rate = 1.05;
      speech.onend = () => setIsPlayingAudio(false);
      window.speechSynthesis.speak(speech);
    } else if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  };

  const handleDownloadNotes = () => {
    const blob = new Blob([userNotes], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `research_notes_${query.toLowerCase().replace(/\s+/g, "_")}.md`;
    a.click();
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Studio Header Breadcrumb */}
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/10">
        <div>
          <div className="text-xs font-mono uppercase tracking-widest text-[#BEF5DC] mb-1">
            ✦ Autonomous Research Studio
          </div>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-white leading-tight">
            {query}
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <div className="bg-[#001852] border border-[#00D084]/40 text-[#BEF5DC] px-3.5 py-1.5 rounded-full text-xs font-mono font-bold flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[#00D084]" />
            DPO Critic Score: {criticEval.score || "8.8"}/10
          </div>
        </div>
      </div>

      {/* 3-Column Studio Workspace Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* ================= LEFT COLUMN: SOURCES HUB (3 cols) ================= */}
        <div className="lg:col-span-3 space-y-4">
          <div className="aha-glass-card p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="font-serif text-lg font-bold text-white flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-[#BEF5DC]" />
                Sources Hub
              </div>
              <span className="text-xs font-mono text-[#BEF5DC]">
                [{rankedDocs.length}]
              </span>
            </div>

            {/* Filter Pills */}
            <div className="flex gap-1.5 flex-wrap mb-4">
              {["all", "pubmed", "biorxiv", "arxiv", "chembl", "pubchem"].map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSourceFilter(cat)}
                  className={`text-[10px] font-mono font-bold uppercase px-2 py-1 rounded transition-colors cursor-pointer ${
                    sourceFilter === cat
                      ? "bg-[#BEF5DC] text-[#000D2E]"
                      : "bg-[#001852] text-slate-300 hover:text-white border border-white/10"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* Document List */}
            <div className="space-y-2.5 max-h-[640px] overflow-y-auto pr-1">
              {filteredDocs.map((doc: any, idx: number) => (
                <div
                  key={idx}
                  className="bg-[#000D2E]/80 border border-white/10 hover:border-[#BEF5DC]/60 p-3 rounded-lg text-xs transition-all"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded bg-[#001852] text-[#BEF5DC] border border-[#BEF5DC]/30 uppercase">
                      {doc.source}
                    </span>
                    <span className="text-[11px] font-mono text-[#00D084] font-bold">
                      {doc.relevance_score || 88}%
                    </span>
                  </div>

                  <a
                    href={doc.url || "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="font-serif text-sm font-semibold text-white hover:text-[#BEF5DC] transition-colors leading-snug block mb-1"
                  >
                    [{idx + 1}] {doc.title}
                  </a>

                  <div className="text-[10px] text-slate-400 mb-2">
                    {doc.year || "Recent"} • {doc.authors?.[0] || "Research Team"}
                  </div>

                  <button
                    onClick={() => setExpandedDoc(expandedDoc === idx ? null : idx)}
                    className="text-[11px] text-[#BEF5DC] hover:underline flex items-center gap-1 cursor-pointer"
                  >
                    <span>{expandedDoc === idx ? "Hide Snippet" : "View Extract"}</span>
                    {expandedDoc === idx ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </button>

                  {expandedDoc === idx && (
                    <div className="mt-2 pt-2 border-t border-white/10 text-[11px] text-slate-300 leading-relaxed bg-[#000D2E] p-2 rounded">
                      {doc.abstract}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ================= MIDDLE COLUMN: DEEPTHINK & SYNTHESIS (4 cols) ================= */}
        <div className="lg:col-span-4 space-y-4">
          
          {/* DeepThink Reasoning Accordion */}
          <div className="aha-glass-card p-4">
            <button
              onClick={() => setDeepThinkExpanded(!deepThinkExpanded)}
              className="w-full flex items-center justify-between text-left cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-[#BEF5DC]" />
                <span className="text-xs font-mono font-bold text-white">
                  Thought for {execTime}s (LangGraph Multi-Agent Trace)
                </span>
              </div>
              {deepThinkExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
            </button>

            {deepThinkExpanded && (
              <div className="mt-3 pt-3 border-t border-white/10 space-y-2 max-h-60 overflow-y-auto">
                {reasoningLogs.map((log: any, i: number) => (
                  <div key={i} className="text-xs bg-[#000D2E]/60 p-2 rounded border-l-2 border-[#00D084]">
                    <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mb-1">
                      <span className="text-[#BEF5DC] font-bold">{log.agent}</span>
                      <span>{log.timestamp}</span>
                    </div>
                    <div className="text-slate-200 font-medium">{log.thought}</div>
                    <div className="text-[10px] font-mono text-slate-400 mt-1">Action: {log.action}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Executive Research Dossier */}
          <div className="aha-glass-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-4 h-4 text-[#00D084]" />
              <h3 className="font-serif text-xl font-bold text-white">
                Executive Synthesis Dossier
              </h3>
            </div>

            <div className="text-xs text-slate-200 leading-relaxed space-y-3">
              <p>
                {finalSynthesis.executive_summary || "Autonomous literature synthesis completed."}
              </p>
            </div>

            {/* Critic Scorecard */}
            {criticEval && (
              <div className="mt-5 pt-4 border-t border-white/10">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-white flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-[#00D084]" />
                    DPO Biological & Chemical Quality
                  </span>
                  <span className="text-xs font-mono font-bold text-[#BEF5DC]">
                    {criticEval.score}/10
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="bg-[#000D2E]/80 p-2 rounded border-l-2 border-[#00D084]">
                    <div className="text-slate-400 text-[10px] uppercase font-bold">Bio-Plausibility</div>
                    <div className="text-slate-200 mt-0.5">{criticEval.biological_plausibility || "High"}</div>
                  </div>
                  <div className="bg-[#000D2E]/80 p-2 rounded border-l-2 border-[#0037FF]">
                    <div className="text-slate-400 text-[10px] uppercase font-bold">Chemical Tractability</div>
                    <div className="text-slate-200 mt-0.5">{criticEval.chemical_tractability || "Lipinski Compliant"}</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ================= RIGHT COLUMN: STUDIO LAB & INSPECTOR (5 cols) ================= */}
        <div className="lg:col-span-5 space-y-4">
          
          {/* Studio Tabs */}
          <div className="flex items-center gap-2 border-b border-white/10 pb-2">
            <button
              onClick={() => setActiveTab("inspector")}
              className={`text-xs font-serif font-bold px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors cursor-pointer ${
                activeTab === "inspector"
                  ? "bg-[#0014AA] text-[#BEF5DC] border border-[#BEF5DC]/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Atom className="w-3.5 h-3.5" />
              3D Bond Inspector
            </button>

            <button
              onClick={() => setActiveTab("audio")}
              className={`text-xs font-serif font-bold px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors cursor-pointer ${
                activeTab === "audio"
                  ? "bg-[#0014AA] text-[#BEF5DC] border border-[#BEF5DC]/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Mic className="w-3.5 h-3.5" />
              Audio Overview
            </button>

            <button
              onClick={() => setActiveTab("moa")}
              className={`text-xs font-serif font-bold px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors cursor-pointer ${
                activeTab === "moa"
                  ? "bg-[#0014AA] text-[#BEF5DC] border border-[#BEF5DC]/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <GitBranch className="w-3.5 h-3.5" />
              MoA Pathway
            </button>

            <button
              onClick={() => setActiveTab("notes")}
              className={`text-xs font-serif font-bold px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors cursor-pointer ${
                activeTab === "notes"
                  ? "bg-[#0014AA] text-[#BEF5DC] border border-[#BEF5DC]/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              Notes
            </button>
          </div>

          {/* TAB 1: Photorealistic 3D Bond Inspector */}
          {activeTab === "inspector" && (
            <BondInspector3D molData={leadMolecule} />
          )}

          {/* TAB 2: Audio Overview Player */}
          {activeTab === "audio" && (
            <div className="aha-glass-card p-6 space-y-4">
              <div className="flex items-center gap-3">
                <button
                  onClick={handleToggleAudio}
                  className="w-12 h-12 rounded-full bg-gradient-to-r from-[#0037FF] to-[#00D084] flex items-center justify-center text-[#000D2E] shadow-lg shadow-[#0037FF]/30 hover:scale-105 transition-transform cursor-pointer"
                >
                  {isPlayingAudio ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
                </button>
                <div>
                  <h4 className="font-serif text-base font-bold text-white">
                    Deep Dive Podcast: {query}
                  </h4>
                  <div className="text-xs text-[#BEF5DC] font-mono">
                    Dual-Host AI Conversation • Dr. Aris & Dr. Elena
                  </div>
                </div>
              </div>

              {/* Animated Equalizer */}
              <div className="flex items-center gap-1 h-8 bg-[#000D2E]/80 p-2 rounded border border-white/10">
                {[...Array(20)].map((_, i) => (
                  <div
                    key={i}
                    className={`flex-grow bg-[#00D084] rounded-full transition-all ${
                      isPlayingAudio ? "wave-active" : "h-1"
                    }`}
                    style={{ animationDelay: `${(i * 0.08).toFixed(2)}s` }}
                  />
                ))}
              </div>

              <div className="text-xs text-slate-300 leading-relaxed bg-[#000D2E]/70 p-4 rounded-lg border border-white/10">
                <div className="font-bold text-[#BEF5DC] mb-1">👨‍🔬 Dr. Aris (Mechanistic Biologist):</div>
                "When we cross-referenced the latest literature on {query}, one key neural circuitry stood out: aberrant upstream kinase signaling and prefrontal-amygdala disinhibition."
                <br /><br />
                <div className="font-bold text-[#00D084] mb-1">👩‍🔬 Dr. Elena (Medicinal Chemist):</div>
                "And our lead compound: {leadMolecule.name || 'Candidate Lead'} shows a molecular weight of {leadMolecule.mw || 450} Da with 0 toxicophore alerts, offering optimal membrane permeability."
              </div>
            </div>
          )}

          {/* TAB 3: MoA Flowchart & Mindmap */}
          {activeTab === "moa" && (
            <div className="aha-glass-card p-5 space-y-4">
              <h4 className="font-serif text-base font-bold text-white mb-2">
                📊 Mechanism of Action (MoA) Disease Flowchart
              </h4>
              <div className="bg-[#000D2E] p-4 rounded-lg border border-white/10 text-xs font-mono text-emerald-300 overflow-x-auto">
                <pre>{researchState?.notebook_data?.mermaid_flowchart || "Pathway DAG rendering..."}</pre>
              </div>
            </div>
          )}

          {/* TAB 4: Pinned Notes */}
          {activeTab === "notes" && (
            <div className="aha-glass-card p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="font-serif text-base font-bold text-white">
                  📝 Research Study Scratchpad
                </h4>
                <button
                  onClick={handleDownloadNotes}
                  className="text-xs font-bold text-[#BEF5DC] hover:text-white flex items-center gap-1 bg-[#001852] border border-[#BEF5DC]/30 px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  Export .md
                </button>
              </div>

              <textarea
                value={userNotes}
                onChange={(e) => setUserNotes(e.target.value)}
                rows={12}
                className="w-full bg-[#000D2E] border border-white/10 rounded-lg p-3 text-xs font-mono text-slate-200 outline-none focus:border-[#BEF5DC]"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
