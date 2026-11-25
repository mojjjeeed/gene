"use client";

import React, { useState } from "react";
import LandingHeroPage from "@/components/LandingHeroPage";
import ConsensusSearch from "@/components/ConsensusSearch";
import A9Workspace from "@/components/A9Workspace";
import DrugDiscoveryWorkspace from "@/components/DrugDiscoveryWorkspace";
import ApiKeyModal from "@/components/ApiKeyModal";
import { useFlags } from "@/lib/useFlags";
import { useTheme } from "@/lib/theme";

type View = "landing" | "consensus" | "workspace";

const DEFAULT_QUERY =
  "Find novel small molecules related to this target and explain why each candidate is worth investigating.";

export default function Home() {
  const [currentView, setCurrentView] = useState<View>("landing");
  const [activeQuery, setActiveQuery] = useState(DEFAULT_QUERY);
  const [isApiKeyModalOpen, setIsApiKeyModalOpen] = useState(false);
  // Which workspace the current launch uses, decided when the user launches (server-evaluated flag).
  const flags = useFlags();
  const [useLiveWorkspace, setUseLiveWorkspace] = useState(false);
  const { theme, toggle: handleToggleTheme } = useTheme();

  const openApiKeys = () => setIsApiKeyModalOpen(true);

  // Landing -> search screen
  const handleStartDiscovering = () => setCurrentView("consensus");

  // Any entry point that launches a research run
  const handleLaunchResearch = (queryText?: string) => {
    if (queryText && queryText.trim()) {
      setActiveQuery(queryText.trim());
    }
    setUseLiveWorkspace(flags.paper_list);
    setCurrentView("workspace");
  };

  return (
    <main className={`min-h-screen ${theme === "dark" ? "dark bg-[#121316]" : "bg-[#FAFAFC]"}`}>
      {currentView === "landing" && (
        <LandingHeroPage
          onStartDiscovering={handleStartDiscovering}
          onLaunchDemo={handleLaunchResearch}
          onOpenApiKeys={openApiKeys}
          theme={theme}
          onToggleTheme={handleToggleTheme}
        />
      )}

      {currentView === "consensus" && (
        <ConsensusSearch
          onSearch={handleLaunchResearch}
          onBackToLanding={() => setCurrentView("landing")}
          onOpenApiKeys={openApiKeys}
          theme={theme}
          onToggleTheme={handleToggleTheme}
        />
      )}

      {currentView === "workspace" && useLiveWorkspace && (
        <A9Workspace
          key={activeQuery}
          initialQuery={activeQuery}
          onBackToSearch={() => setCurrentView("consensus")}
          onOpenApiKeys={openApiKeys}
          theme={theme}
          onToggleTheme={handleToggleTheme}
        />
      )}

      {currentView === "workspace" && !useLiveWorkspace && (
        <DrugDiscoveryWorkspace
          // Remount per query so every launch starts from a clean loading state
          key={activeQuery}
          initialQuery={activeQuery}
          onBackToSearch={() => setCurrentView("consensus")}
          onOpenApiKeys={openApiKeys}
          theme={theme}
          onToggleTheme={handleToggleTheme}
        />
      )}

      <ApiKeyModal isOpen={isApiKeyModalOpen} onClose={() => setIsApiKeyModalOpen(false)} />
    </main>
  );
}
