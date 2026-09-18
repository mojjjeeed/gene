"use client";

import React from "react";
import { Sparkles, Database, BookOpen, Atom, ArrowLeft } from "lucide-react";

interface NavbarProps {
  currentView: "landing" | "studio";
  activeQuery: string;
  onBackToLanding: () => void;
}

export default function Navbar({ currentView, activeQuery, onBackToLanding }: NavbarProps) {
  return (
    <header className="sticky top-0 z-50 bg-[#000D2E]/90 border-b border-[#BEF5DC]/20 backdrop-blur-md px-6 py-3.5 transition-all">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand Logo & Editorial Title */}
        <div className="flex items-center gap-4">
          <div 
            onClick={onBackToLanding}
            className="cursor-pointer flex items-center gap-2.5 group"
          >
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#0037FF] to-[#00D084] flex items-center justify-center shadow-lg shadow-[#0037FF]/30 group-hover:scale-105 transition-transform">
              <Atom className="w-5 h-5 text-[#000D2E]" />
            </div>
            <div>
              <div className="font-serif text-lg font-bold text-white tracking-tight flex items-center gap-2">
                BioResearch <span className="text-[#BEF5DC] italic font-normal">AI Studio</span>
              </div>
              <div className="text-[10px] text-[#BEF5DC]/70 font-mono uppercase tracking-widest">
                AHA Intelligence Platform
              </div>
            </div>
          </div>

          {currentView === "studio" && (
            <div className="hidden md:flex items-center gap-2 pl-4 border-l border-white/10">
              <button 
                onClick={onBackToLanding}
                className="text-xs text-slate-400 hover:text-white flex items-center gap-1 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> All Studies
              </button>
              <span className="text-slate-600">/</span>
              <span className="text-xs font-serif italic text-[#BEF5DC] truncate max-w-[280px]">
                {activeQuery}
              </span>
            </div>
          )}
        </div>

        {/* Global Status Badges */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 text-xs font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-500/30 px-3 py-1 rounded-full">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            LangGraph + RDKit Active
          </div>

          <div className="flex items-center gap-1.5 text-xs text-slate-300 bg-[#001852] border border-[#BEF5DC]/20 px-3 py-1 rounded-full">
            <Database className="w-3.5 h-3.5 text-[#00D084]" />
            <span>6 Repositories Indexed</span>
          </div>
        </div>
      </div>
    </header>
  );
}
