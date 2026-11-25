import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans, JetBrains_Mono, Inter_Tight, IBM_Plex_Mono, Doto, Newsreader } from "next/font/google";
import "./globals.css";

// Self-hosted by next/font: no render-blocking request to Google Fonts and no layout shift.
const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-jakarta",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

// Landing-page typefaces: neo-grotesk text, a mono for labels, and a dot-matrix face for accent words.
const grotesk = Inter_Tight({ subsets: ["latin"], variable: "--font-grotesk", display: "swap" });
const plexMono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex", display: "swap" });
const doto = Doto({ subsets: ["latin"], variable: "--font-doto", display: "swap" });
const bookSerif = Newsreader({ subsets: ["latin"], style: ["normal", "italic"], variable: "--font-book", display: "swap" });

export const metadata: Metadata = {
  title: "BioResearch AI | Biomedical Research & Drug Discovery Workspace",
  description:
    "Search PubMed, bioRxiv, arXiv, ChEMBL, PubChem and ClinicalTrials.gov in one place and get a cited research briefing for any biomedical target.",
  icons: {
    icon: "/favicon.ico",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FAFAFC" },
    { media: "(prefers-color-scheme: dark)", color: "#121316" },
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // suppressHydrationWarning: useTheme() toggles the `dark` class / color-scheme on <html> after hydration.
    <html
      lang="en"
      className={`h-full antialiased ${jakarta.variable} ${jetbrains.variable} ${grotesk.variable} ${plexMono.variable} ${doto.variable} ${bookSerif.variable}`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col bg-white text-slate-900 selection:bg-blue-600 selection:text-white">
        {children}
      </body>
    </html>
  );
}
