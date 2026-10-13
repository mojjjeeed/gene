"use client";

import React, { useState } from "react";
import { ExternalLink, BookOpen, Sparkles } from "lucide-react";

export interface CitationItem {
  citation_index: number;
  id: string;
  title: string;
  source: string;
  authors: string[] | string;
  year: string;
  url: string;
  doi?: string;
  pmid?: string;
  abstract?: string;
  evidence_quote?: string;
}

interface HoverCitationBadgeProps {
  citationIndex: number;
  citationData?: CitationItem;
  theme?: "light" | "dark";
  onSelectSource?: (citation: CitationItem) => void;
}

export default function HoverCitationBadge({
  citationIndex,
  citationData,
  theme = "dark",
  onSelectSource
}: HoverCitationBadgeProps) {
  const [isHovered, setIsHovered] = useState(false);
  const isDark = theme === "dark";

  const authorsStr = Array.isArray(citationData?.authors)
    ? citationData.authors.join(", ")
    : citationData?.authors || "Primary Investigators";

  const getSourceBadgeStyle = (source?: string) => {
    const s = source?.toLowerCase() || "";
    if (s.includes("pubmed")) return isDark ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" : "bg-emerald-50 text-emerald-700 border-emerald-200";
    if (s.includes("biorxiv")) return isDark ? "bg-purple-500/20 text-purple-300 border-purple-500/40" : "bg-purple-50 text-purple-700 border-purple-200";
    if (s.includes("chembl")) return isDark ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40" : "bg-cyan-50 text-cyan-700 border-cyan-200";
    if (s.includes("arxiv")) return isDark ? "bg-rose-500/20 text-rose-300 border-rose-500/40" : "bg-rose-50 text-rose-700 border-rose-200";
    if (s.includes("nature")) return isDark ? "bg-amber-500/20 text-amber-300 border-amber-500/40" : "bg-amber-50 text-amber-700 border-amber-200";
    return isDark ? "bg-blue-500/20 text-blue-300 border-blue-500/40" : "bg-blue-50 text-blue-700 border-blue-200";
  };

  return (
    <span 
      className="relative inline-block align-baseline mx-0.5 select-none"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Citation Pill Badge (NotebookLM Style) */}
      <button
        type="button"
        onClick={() => citationData && onSelectSource?.(citationData)}
        className={`inline-flex items-center justify-center px-1.5 py-0.2 rounded-full text-[11px] font-mono font-bold transition-all cursor-pointer shadow-sm hover:scale-110 active:scale-95 ${
          isDark
            ? "text-blue-400 bg-blue-500/15 hover:bg-blue-500/30 border border-blue-500/30 hover:border-blue-400"
            : "text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 hover:border-blue-400 font-extrabold"
        }`}
      >
        [{citationIndex}]
      </button>

      {/* Hover Popover Card */}
      {isHovered && citationData && (
        <div 
          className={`absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-80 sm:w-96 p-3.5 rounded-xl shadow-2xl backdrop-blur-xl z-50 text-left pointer-events-auto animate-fadeIn ${
            isDark
              ? "bg-[#18191E] border border-white/15 text-white"
              : "bg-white border border-slate-200 text-slate-900 shadow-slate-300/80"
          }`}
          style={{
            boxShadow: isDark
              ? "0 20px 40px -10px rgba(0, 0, 0, 0.7), 0 0 20px rgba(59, 130, 246, 0.15)"
              : "0 20px 35px -5px rgba(0, 0, 0, 0.15), 0 0 1px rgba(0, 0, 0, 0.2)"
          }}
        >
          {/* Arrow */}
          <div 
            className={`absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-8 border-transparent pointer-events-none ${
              isDark ? "border-t-[#18191E]" : "border-t-white"
            }`} 
          />

          {/* Top Row: Source & Year */}
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase tracking-wider border ${getSourceBadgeStyle(citationData.source)}`}>
              {citationData.source}
            </span>
            <span className={`text-[10px] font-mono ${isDark ? "text-slate-400" : "text-slate-500"}`}>
              {citationData.year}
            </span>
          </div>

          {/* Paper Title */}
          <h4 className={`text-xs font-bold leading-snug mb-1 ${isDark ? "text-white" : "text-slate-900"}`}>
            {citationData.title}
          </h4>

          {/* Authors */}
          <p className={`text-[10px] line-clamp-1 mb-2 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
            {authorsStr}
          </p>

          {/* Grounded Evidence Quote from Resource */}
          {citationData.evidence_quote && (
            <div className={`p-2.5 my-2 rounded-lg border ${
              isDark 
                ? "bg-[#121316] border-white/5" 
                : "bg-slate-50 border-slate-200/80"
            }`}>
              <span className={`text-[9px] font-mono uppercase tracking-wider block mb-0.5 flex items-center gap-1 ${
                isDark ? "text-cyan-400" : "text-blue-600 font-bold"
              }`}>
                <Sparkles className="w-2.5 h-2.5" />
                Grounded Literature Evidence:
              </span>
              <p className={`text-[11px] leading-relaxed italic ${isDark ? "text-slate-200" : "text-slate-800"}`}>
                "{citationData.evidence_quote}"
              </p>
            </div>
          )}

          {/* Actions Bar */}
          <div className={`pt-2 border-t flex items-center justify-between text-[11px] ${
            isDark ? "border-white/10" : "border-slate-100"
          }`}>
            <button
              type="button"
              onClick={() => onSelectSource?.(citationData)}
              className="text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 font-semibold flex items-center gap-1 cursor-pointer"
            >
              <BookOpen className="w-3 h-3" />
              <span>Inspect Source</span>
            </button>

            {citationData.url && (
              <a
                href={citationData.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`flex items-center gap-1 font-mono text-[10px] transition-colors ${
                  isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900"
                }`}
              >
                <span>External Link</span>
                <ExternalLink className="w-2.5 h-2.5" />
              </a>
            )}
          </div>
        </div>
      )}
    </span>
  );
}
