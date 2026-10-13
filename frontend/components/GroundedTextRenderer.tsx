"use client";

import React from "react";
import HoverCitationBadge, { CitationItem } from "./HoverCitationBadge";

interface GroundedTextRendererProps {
  content: string;
  citations: CitationItem[];
  theme?: "light" | "dark";
  onSelectSource?: (citation: CitationItem) => void;
}

export default function GroundedTextRenderer({
  content,
  citations,
  theme = "dark",
  onSelectSource
}: GroundedTextRendererProps) {
  const isDark = theme === "dark";

  // Map citations by index for O(1) lookup
  const citationMap = new Map<number, CitationItem>();
  citations.forEach((c) => {
    citationMap.set(c.citation_index, c);
  });

  // Split lines (handling bullet points and paragraphs)
  const lines = content.split("\n");

  return (
    <div className={`space-y-3 leading-relaxed text-sm sm:text-[15px] ${
      isDark ? "text-slate-300" : "text-slate-700"
    }`}>
      {lines.map((line, lineIdx) => {
        if (!line.trim()) return null;

        const isBullet = line.trim().startsWith("- ") || line.trim().startsWith("• ");
        const textToParse = isBullet ? line.trim().substring(2) : line;

        // Parse citation tags [1], [2], etc.
        const parts = textToParse.split(/(\[\d+\])/g);

        const renderedLine = (
          <span key={`line-${lineIdx}`}>
            {parts.map((part, partIdx) => {
              const match = part.match(/^\[(\d+)\]$/);
              if (match) {
                const citationNum = parseInt(match[1], 10);
                const citationData = citationMap.get(citationNum);

                return (
                  <HoverCitationBadge
                    key={`cite-${partIdx}`}
                    citationIndex={citationNum}
                    citationData={citationData}
                    theme={theme}
                    onSelectSource={onSelectSource}
                  />
                );
              }

              // Simple markdown bold renderer
              const boldParts = part.split(/(\*\*.*?\*\*)/g);
              return (
                <span key={`text-${partIdx}`}>
                  {boldParts.map((bPart, bIdx) => {
                    if (bPart.startsWith("**") && bPart.endsWith("**")) {
                      return (
                        <b 
                          key={`b-${bIdx}`} 
                          className={`font-semibold ${isDark ? "text-white" : "text-slate-900"}`}
                        >
                          {bPart.slice(2, -2)}
                        </b>
                      );
                    }
                    return bPart;
                  })}
                </span>
              );
            })}
          </span>
        );

        if (isBullet) {
          return (
            <div key={`bullet-${lineIdx}`} className="flex items-start gap-2.5 pl-2">
              <span className={`w-1.5 h-1.5 rounded-full mt-2 shrink-0 ${
                isDark ? "bg-blue-400" : "bg-blue-600"
              }`} />
              <div className="flex-1">{renderedLine}</div>
            </div>
          );
        }

        return (
          <p key={`p-${lineIdx}`} className={isDark ? "text-slate-300" : "text-slate-700"}>
            {renderedLine}
          </p>
        );
      })}
    </div>
  );
}
