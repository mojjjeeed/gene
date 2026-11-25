"use client";

import React, { useCallback, useEffect, useId, useRef, useState } from "react";
import { ExternalLink, BookOpen, Sparkles } from "lucide-react";
import { sourceBadgeClass, formatAuthors, type CitationItem } from "@/lib/research";

// Re-exported so existing imports from this module keep working.
export type { CitationItem };

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
  onSelectSource,
}: HoverCitationBadgeProps) {
  const [isOpen, setIsOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const popoverId = useId();
  const isDark = theme === "dark";

  const open = useCallback(() => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setIsOpen(true);
  }, []);

  // Small delay so the pointer can travel from the badge into the popover without it vanishing.
  const closeSoon = useCallback(() => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setIsOpen(false), 120);
  }, []);

  useEffect(() => () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [isOpen]);

  // Keep the popover inside the viewport (citations near the screen edge used to get clipped).
  // Mutates the DOM node directly, so no extra render is needed.
  const keepInViewport = useCallback((el: HTMLDivElement | null) => {
    if (!el) return;
    el.style.transform = "translateX(-50%)";
    const rect = el.getBoundingClientRect();
    const margin = 12;
    let shift = 0;
    if (rect.left < margin) shift = margin - rect.left;
    else if (rect.right > window.innerWidth - margin) shift = window.innerWidth - margin - rect.right;
    if (shift) el.style.transform = `translateX(calc(-50% + ${Math.round(shift)}px))`;
  }, []);

  const authors = formatAuthors(citationData?.authors) || "Authors not listed";

  return (
    <span
      className="relative inline-block align-baseline mx-0.5"
      onMouseEnter={open}
      onMouseLeave={closeSoon}
      onFocus={open}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) closeSoon();
      }}
    >
      <button
        type="button"
        onClick={() => citationData && onSelectSource?.(citationData)}
        aria-describedby={isOpen && citationData ? popoverId : undefined}
        aria-label={`Citation ${citationIndex}${citationData ? `: ${citationData.title}` : ""}`}
        className={`inline-flex items-center justify-center px-1.5 rounded-full text-[11px] leading-5 font-mono font-bold transition-all active:scale-95 border ${
          isDark
            ? "text-blue-300 bg-blue-500/15 hover:bg-blue-500/30 border-blue-500/30 hover:border-blue-400"
            : "text-blue-700 bg-blue-50 hover:bg-blue-100 border-blue-200 hover:border-blue-400"
        }`}
      >
        {citationIndex}
      </button>

      {isOpen && citationData && (
        // pt-2 (not margin) keeps the hover area continuous between badge and card.
        <div
          id={popoverId}
          role="tooltip"
          ref={keepInViewport}
          className="absolute bottom-full left-1/2 pb-2 w-[22rem] max-w-[calc(100vw-1.5rem)] z-50 text-left"
          style={{ transform: "translateX(-50%)" }}
        >
          <div
            className={`relative p-3.5 rounded-xl backdrop-blur-xl animate-fadeIn ${
              isDark
                ? "bg-[#18191E] border border-white/15 text-white"
                : "bg-white border border-slate-200 text-slate-900"
            }`}
            style={{
              boxShadow: isDark
                ? "0 20px 40px -10px rgba(0, 0, 0, 0.7), 0 0 20px rgba(59, 130, 246, 0.12)"
                : "0 20px 35px -5px rgba(15, 23, 42, 0.15), 0 0 1px rgba(15, 23, 42, 0.2)",
            }}
          >
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase tracking-wider border ${sourceBadgeClass(citationData.source, isDark)}`}>
                {citationData.source}
              </span>
              <span className={`text-[10px] font-mono ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                {citationData.year}
              </span>
            </div>

            <h4 className={`text-xs font-bold leading-snug mb-1 ${isDark ? "text-white" : "text-slate-900"}`}>
              {citationData.title}
            </h4>

            <p className={`text-[10px] line-clamp-1 mb-2 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
              {authors}
            </p>

            {citationData.evidence_quote && (
              <div className={`p-2.5 my-2 rounded-lg border ${isDark ? "bg-[#121316] border-white/5" : "bg-slate-50 border-slate-200/80"}`}>
                <span className={`text-[9px] font-mono uppercase tracking-wider mb-0.5 flex items-center gap-1 ${isDark ? "text-cyan-400" : "text-blue-600 font-bold"}`}>
                  <Sparkles className="w-2.5 h-2.5" aria-hidden="true" />
                  Excerpt from source
                </span>
                <p className={`text-[11px] leading-relaxed italic line-clamp-4 ${isDark ? "text-slate-200" : "text-slate-800"}`}>
                  &ldquo;{citationData.evidence_quote}&rdquo;
                </p>
              </div>
            )}

            <div className={`pt-2 border-t flex items-center justify-between text-[11px] ${isDark ? "border-white/10" : "border-slate-100"}`}>
              <button
                type="button"
                onClick={() => onSelectSource?.(citationData)}
                className="text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 font-semibold flex items-center gap-1"
              >
                <BookOpen className="w-3 h-3" aria-hidden="true" />
                <span>Inspect source</span>
              </button>

              {citationData.url && (
                <a
                  href={citationData.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`flex items-center gap-1 font-mono text-[10px] transition-colors ${isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900"}`}
                >
                  <span>Open</span>
                  <ExternalLink className="w-2.5 h-2.5" aria-hidden="true" />
                </a>
              )}
            </div>

            {/* Arrow */}
            <div
              aria-hidden="true"
              className={`absolute top-full left-1/2 -translate-x-1/2 -mt-px w-3 h-3 rotate-45 -translate-y-1.5 border-r border-b ${
                isDark ? "bg-[#18191E] border-white/15" : "bg-white border-slate-200"
              }`}
            />
          </div>
        </div>
      )}
    </span>
  );
}
