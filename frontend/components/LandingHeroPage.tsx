"use client";

import React from "react";
import "./landing/landing.css";
import {
  ActivityPanel,
  Announcement,
  CtaCard,
  Faq,
  Footer,
  Hero,
  Nav,
  PathGrid,
  Pipeline,
  QueryWall,
  SourceMarquee,
  Tiles,
  Workflow,
} from "./landing/sections";

interface LandingHeroPageProps {
  onStartDiscovering: () => void;
  onLaunchDemo: (query?: string) => void;
  onOpenApiKeys: () => void;
  theme?: "light" | "dark";
  onToggleTheme?: () => void;
}

/** Marketing landing page. Section components live in ./landing/sections.tsx; styles in ./landing/landing.css. */
export default function LandingHeroPage({
  onStartDiscovering,
  onLaunchDemo,
  onOpenApiKeys,
  theme = "light",
  onToggleTheme,
}: LandingHeroPageProps) {
  const actions = { onStart: onStartDiscovering, onLaunch: onLaunchDemo, onOpenKeys: onOpenApiKeys };

  return (
    <div className="fo" data-theme={theme}>
      <Announcement onStart={onStartDiscovering} />
      <Nav onStart={onStartDiscovering} theme={theme} onToggleTheme={onToggleTheme} />
      <main>
        <Hero {...actions} />
        <SourceMarquee />
        <PathGrid {...actions} />
        <QueryWall onLaunch={onLaunchDemo} />
        <Workflow {...actions} />
        <Tiles {...actions} />
        <Pipeline {...actions} />
        <ActivityPanel {...actions} />
        <Faq />
        <CtaCard onStart={onStartDiscovering} />
      </main>
      <Footer {...actions} />
    </div>
  );
}
