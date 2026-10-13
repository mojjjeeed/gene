"use client";

import React, { useState, useEffect } from "react";
import LandingHeroPage from "@/components/LandingHeroPage";
import ConsensusSearch from "@/components/ConsensusSearch";
import DrugDiscoveryWorkspace from "@/components/DrugDiscoveryWorkspace";
import ApiKeyModal from "@/components/ApiKeyModal";

export default function Home() {
  const [currentView, setCurrentView] = useState<"landing" | "consensus" | "workspace">("landing");
  const [activeQuery, setActiveQuery] = useState(
    "Find novel small molecules related to this target and explain why each candidate is worth investigating."
  );
  const [isApiKeyModalOpen, setIsApiKeyModalOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  // Load saved theme preference
  useEffect(() => {
    if (typeof window !== "undefined") {
      const savedTheme = localStorage.getItem("BIORESEARCH_THEME") as "light" | "dark" | null;
      if (savedTheme) {
        setTheme(savedTheme);
      }
    }
  }, []);

  const handleToggleTheme = () => {
    setTheme((prev) => {
      const nextTheme = prev === "dark" ? "light" : "dark";
      if (typeof window !== "undefined") {
        localStorage.setItem("BIORESEARCH_THEME", nextTheme);
      }
      return nextTheme;
    });
  };

  // Transition to Consensus Search (Image 2)
  const handleStartDiscovering = () => {
    setCurrentView("consensus");
  };

  // Launch live research / demo (Image 3)
  const handleLaunchResearch = (queryText?: string) => {
    if (queryText && queryText.trim()) {
      setActiveQuery(queryText.trim());
    }
    setCurrentView("workspace");
  };

  return (
    <main className={`min-h-screen ${theme === "dark" ? "dark bg-[#121316]" : "bg-[#FAFAFC]"}`}>
      {/* View 1: Landing Page (Image 1) */}
      {currentView === "landing" && (
        <LandingHeroPage
          onStartDiscovering={handleStartDiscovering}
          onLaunchDemo={handleLaunchResearch}
          onOpenApiKeys={() => setIsApiKeyModalOpen(true)}
          theme={theme}
          onToggleTheme={handleToggleTheme}
        />
      )}

      {/* View 2: Consensus Search Interface (Image 2) */}
      {currentView === "consensus" && (
        <ConsensusSearch
          onSearch={handleLaunchResearch}
          onBackToLanding={() => setCurrentView("landing")}
          onOpenApiKeys={() => setIsApiKeyModalOpen(true)}
          theme={theme}
          onToggleTheme={handleToggleTheme}
        />
      )}

      {/* View 3: Live Drug Discovery Agent & NotebookLM Workspace (Image 3) */}
      {currentView === "workspace" && (
        <DrugDiscoveryWorkspace
          initialQuery={activeQuery}
          onBackToSearch={() => setCurrentView("consensus")}
          onOpenApiKeys={() => setIsApiKeyModalOpen(true)}
          theme={theme}
          onToggleTheme={handleToggleTheme}
        />
      )}

      {/* AI Key & Model Settings Modal */}
      <ApiKeyModal
        isOpen={isApiKeyModalOpen}
        onClose={() => setIsApiKeyModalOpen(false)}
      />
    </main>
  );
}
