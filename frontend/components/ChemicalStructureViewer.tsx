"use client";

import React, { useState, useEffect, useRef } from "react";
import { RotateCw, ZoomIn, ZoomOut, Maximize2, Sparkles, Layers } from "lucide-react";

export interface MoleculeData {
  id: string;
  name: string;
  code: string;
  relevance: number;
  category: string;
  smiles: string;
  mw: number;
  logp: number;
  hbd: number;
  hba: number;
  tpsa: number;
  rotatableBonds: number;
  formula: string;
  dockingScore: string;
  ic50: string;
  kd: string;
  targetResidue: string;
  evidenceSummary: string;
  atoms: Array<{
    id: number;
    symbol: string;
    x: number;
    y: number;
    z?: number;
    charge?: number;
    hybridization?: string;
  }>;
  bonds: Array<{
    from: number;
    to: number;
    type: "single" | "double" | "aromatic";
  }>;
}

export const PRESET_MOLECULES: Record<string, MoleculeData> = {
  "Candidate A-17": {
    id: "candidate-a17",
    name: "Candidate A-17",
    code: "DISC-0017 · predicted hit",
    relevance: 91,
    category: "4th-Gen EGFR Kinase Inhibitor",
    smiles: "CN1C=CC(=C1)C2=NC(=O)N(C2)CCO",
    mw: 382.40,
    logp: 2.80,
    hbd: 2,
    hba: 5,
    tpsa: 74.2,
    rotatableBonds: 4,
    formula: "C18H22N4O2",
    dockingScore: "-9.4 kcal/mol",
    ic50: "4.2 nM",
    kd: "2.1 nM",
    targetResidue: "Met793 (hinge) & Lys745",
    evidenceSummary: "Exhibits picomolar potency against EGFR T790M/C797S double mutant with >50x window over wild-type kinase. Favorable metabolic clearance in human liver microsomes.",
    atoms: [
      { id: 0, symbol: "N", x: 45, y: 110, z: -10, hybridization: "sp2" },
      { id: 1, symbol: "C", x: 80, y: 70, z: -5, hybridization: "sp2" },
      { id: 2, symbol: "C", x: 125, y: 90, z: 0, hybridization: "sp2" },
      { id: 3, symbol: "O", x: 165, y: 65, z: 12, hybridization: "sp2" },
      { id: 4, symbol: "N", x: 195, y: 110, z: -8, hybridization: "sp2" },
      { id: 5, symbol: "C", x: 165, y: 155, z: 5, hybridization: "sp3" },
      { id: 6, symbol: "C", x: 115, y: 145, z: -2, hybridization: "sp2" },
    ],
    bonds: [
      { from: 0, to: 1, type: "single" },
      { from: 1, to: 2, type: "double" },
      { from: 2, to: 3, type: "double" },
      { from: 2, to: 4, type: "single" },
      { from: 4, to: 5, type: "single" },
      { from: 5, to: 6, type: "single" },
      { from: 6, to: 0, type: "aromatic" },
    ]
  },
  "Candidate B-04": {
    id: "candidate-b04",
    name: "Candidate B-04",
    code: "DISC-0004 · analog",
    relevance: 86,
    category: "Allosteric Pocket Ligand",
    smiles: "CC1=NC=CC(=C1)C2=NC3=CC=CC=C3N2",
    mw: 345.18,
    logp: 3.15,
    hbd: 1,
    hba: 4,
    tpsa: 58.4,
    rotatableBonds: 3,
    formula: "C17H15N3O",
    dockingScore: "-8.8 kcal/mol",
    ic50: "12.8 nM",
    kd: "6.4 nM",
    targetResidue: "Leu718 & Phe723",
    evidenceSummary: "Binds with high selectivity into the adjacent induced-fit hydrophobic pouch, sparing peripheral cardiac hERG channels.",
    atoms: [
      { id: 0, symbol: "C", x: 40, y: 100, z: 0, hybridization: "sp2" },
      { id: 1, symbol: "C", x: 75, y: 65, z: -10, hybridization: "sp2" },
      { id: 2, symbol: "C", x: 120, y: 80, z: 10, hybridization: "sp2" },
      { id: 3, symbol: "N", x: 155, y: 115, z: -5, hybridization: "sp2" },
      { id: 4, symbol: "O", x: 195, y: 145, z: 15, hybridization: "sp2" },
      { id: 5, symbol: "C", x: 105, y: 150, z: 5, hybridization: "sp2" },
      { id: 6, symbol: "C", x: 65, y: 140, z: -5, hybridization: "sp2" },
    ],
    bonds: [
      { from: 0, to: 1, type: "single" },
      { from: 1, to: 2, type: "aromatic" },
      { from: 2, to: 3, type: "single" },
      { from: 3, to: 4, type: "double" },
      { from: 3, to: 5, type: "single" },
      { from: 5, to: 6, type: "aromatic" },
      { from: 6, to: 0, type: "single" },
    ]
  },
  "Candidate C-22": {
    id: "candidate-c22",
    name: "Candidate C-22",
    code: "DISC-0022 · macrocycle",
    relevance: 94,
    category: "Macrocyclic Conformer Lead",
    smiles: "CC(C)OC1=CC2=C(C=C1)N=CN=C2NC3=CC(F)=CC=C3",
    mw: 412.35,
    logp: 2.45,
    hbd: 2,
    hba: 6,
    tpsa: 82.1,
    rotatableBonds: 2,
    formula: "C21H21FN4O2",
    dockingScore: "-10.1 kcal/mol",
    ic50: "1.9 nM",
    kd: "0.85 nM",
    targetResidue: "Met793, Thr790 & Asp855",
    evidenceSummary: "Macrocyclization reduces entropic penalty upon target engagement, resulting in sub-nanomolar affinity against triple-resistant NSCLC cells.",
    atoms: [
      { id: 0, symbol: "N", x: 50, y: 120, z: 0, hybridization: "sp2" },
      { id: 1, symbol: "C", x: 80, y: 80, z: 10, hybridization: "sp2" },
      { id: 2, symbol: "N", x: 125, y: 70, z: -10, hybridization: "sp2" },
      { id: 3, symbol: "C", x: 165, y: 95, z: 5, hybridization: "sp2" },
      { id: 4, symbol: "F", x: 205, y: 75, z: 0, hybridization: "sp3" },
      { id: 5, symbol: "O", x: 180, y: 140, z: 15, hybridization: "sp2" },
      { id: 6, symbol: "C", x: 130, y: 155, z: -5, hybridization: "sp3" },
      { id: 7, symbol: "C", x: 85, y: 145, z: 0, hybridization: "sp2" },
    ],
    bonds: [
      { from: 0, to: 1, type: "double" },
      { from: 1, to: 2, type: "single" },
      { from: 2, to: 3, type: "double" },
      { from: 3, to: 4, type: "single" },
      { from: 3, to: 5, type: "single" },
      { from: 5, to: 6, type: "single" },
      { from: 6, to: 7, type: "single" },
      { from: 7, to: 0, type: "single" },
    ]
  },
  "Candidate D-09": {
    id: "candidate-d09",
    name: "Candidate D-09",
    code: "DISC-0009 · covalent warhead",
    relevance: 89,
    category: "Targeted Covalent Inactivator",
    smiles: "C=CC(=O)NC1=CC(=C(C=C1)NC2=NC=NC3=CC=CC=C32)OC",
    mw: 396.44,
    logp: 2.92,
    hbd: 2,
    hba: 5,
    tpsa: 78.5,
    rotatableBonds: 5,
    formula: "C20H20N4O3",
    dockingScore: "-9.8 kcal/mol",
    ic50: "3.4 nM",
    kd: "1.2 nM",
    targetResidue: "Cys797 (Michael addition)",
    evidenceSummary: "Incorporates an optimized acrylamide warhead positioned for rapid electrophilic attack on nucleophilic Cys797 thiol group with 100% covalent occupancy.",
    atoms: [
      { id: 0, symbol: "C", x: 40, y: 80, z: -5, hybridization: "sp2" },
      { id: 1, symbol: "C", x: 80, y: 105, z: 5, hybridization: "sp2" },
      { id: 2, symbol: "O", x: 80, y: 150, z: 10, hybridization: "sp2" },
      { id: 3, symbol: "N", x: 125, y: 90, z: -5, hybridization: "sp2" },
      { id: 4, symbol: "C", x: 165, y: 110, z: 0, hybridization: "sp2" },
      { id: 5, symbol: "C", x: 195, y: 75, z: 8, hybridization: "sp2" },
      { id: 6, symbol: "N", x: 195, y: 150, z: -8, hybridization: "sp2" },
    ],
    bonds: [
      { from: 0, to: 1, type: "double" },
      { from: 1, to: 2, type: "double" },
      { from: 1, to: 3, type: "single" },
      { from: 3, to: 4, type: "single" },
      { from: 4, to: 5, type: "double" },
      { from: 4, to: 6, type: "single" },
    ]
  }
};

interface ChemicalStructureViewerProps {
  molecule?: MoleculeData;
  moleculeName?: string;
  isCompact?: boolean;
  theme?: "dark" | "light";
}

export default function ChemicalStructureViewer({
  molecule,
  moleculeName = "Candidate A-17",
  isCompact = false,
  theme = "dark"
}: ChemicalStructureViewerProps) {
  const currentMol = molecule || PRESET_MOLECULES[moleculeName] || PRESET_MOLECULES["Candidate A-17"];
  const [viewMode, setViewMode] = useState<"2d" | "3d">("2d");
  const [hoveredAtom, setHoveredAtom] = useState<any | null>(null);
  const [rotation, setRotation] = useState({ x: 15, y: 25 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // 3D Canvas animation loop
  useEffect(() => {
    if (viewMode !== "3d" || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let autoAngle = 0;

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const cx = canvas.width / 2;
      const cy = canvas.height / 2;
      const radX = ((rotation.x + Math.sin(autoAngle) * 8) * Math.PI) / 180;
      const radY = ((rotation.y + autoAngle * 30) * Math.PI) / 180;

      // Project 3D atoms
      const projected = currentMol.atoms.map((a) => {
        const x0 = (a.x - 120) * 1.1;
        const y0 = (a.y - 110) * 1.1;
        const z0 = (a.z || 0) * 2;

        // Rotate Y
        const x1 = x0 * Math.cos(radY) + z0 * Math.sin(radY);
        const z1 = -x0 * Math.sin(radY) + z0 * Math.cos(radY);

        // Rotate X
        const y2 = y0 * Math.cos(radX) - z1 * Math.sin(radX);
        const z2 = y0 * Math.sin(radX) + z1 * Math.cos(radX);

        const scale = 200 / (200 + z2);
        return {
          ...a,
          px: cx + x1 * scale,
          py: cy + y2 * scale,
          pz: z2,
          scale,
        };
      });

      // Sort bonds & atoms by Z for depth
      projected.sort((a, b) => a.pz - b.pz);

      // Draw Bonds
      ctx.lineWidth = 3.5;
      currentMol.bonds.forEach((b) => {
        const a1 = projected.find((p) => p.id === b.from);
        const a2 = projected.find((p) => p.id === b.to);
        if (!a1 || !a2) return;

        const grad = ctx.createLinearGradient(a1.px, a1.py, a2.px, a2.py);
        grad.addColorStop(0, getAtomColor(a1.symbol, 0.7));
        grad.addColorStop(1, getAtomColor(a2.symbol, 0.7));

        ctx.strokeStyle = grad;
        ctx.beginPath();
        ctx.moveTo(a1.px, a1.py);
        ctx.lineTo(a2.px, a2.py);
        ctx.stroke();

        if (b.type === "double") {
          ctx.lineWidth = 1.5;
          ctx.strokeStyle = "rgba(255,255,255,0.4)";
          ctx.beginPath();
          ctx.moveTo(a1.px + 3, a1.py + 3);
          ctx.lineTo(a2.px + 3, a2.py + 3);
          ctx.stroke();
          ctx.lineWidth = 3.5;
        }
      });

      // Draw Atoms
      projected.forEach((a) => {
        const radius = Math.max(7, 12 * a.scale);
        const color = getAtomColor(a.symbol);

        // Radial glow
        const radGrad = ctx.createRadialGradient(
          a.px - radius * 0.3,
          a.py - radius * 0.3,
          radius * 0.1,
          a.px,
          a.py,
          radius
        );
        radGrad.addColorStop(0, "#ffffff");
        radGrad.addColorStop(0.3, color);
        radGrad.addColorStop(1, "#0a0a0f");

        ctx.beginPath();
        ctx.arc(a.px, a.py, radius, 0, Math.PI * 2);
        ctx.fillStyle = radGrad;
        ctx.shadowColor = color;
        ctx.shadowBlur = 10;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Label
        ctx.fillStyle = "#ffffff";
        ctx.font = `bold ${Math.max(9, Math.round(10 * a.scale))}px Inter, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(a.symbol, a.px, a.py);
      });

      autoAngle += 0.008;
      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [viewMode, rotation, currentMol]);

  const getAtomColor = (sym: string, alpha = 1) => {
    switch (sym) {
      case "N": return `rgba(59, 130, 246, ${alpha})`;
      case "O": return `rgba(239, 68, 68, ${alpha})`;
      case "F": return `rgba(16, 185, 129, ${alpha})`;
      case "C": return `rgba(148, 163, 184, ${alpha})`;
      default: return `rgba(168, 85, 247, ${alpha})`;
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStart.current.x;
    const dy = e.clientY - dragStart.current.y;
    setRotation((prev) => ({
      x: prev.x - dy * 0.5,
      y: prev.y + dx * 0.5,
    }));
    dragStart.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseUp = () => setIsDragging(false);

  return (
    <div className={`relative rounded-xl overflow-hidden border ${
      theme === "dark" 
        ? "bg-[#18191E] border-white/10" 
        : "bg-white border-slate-200 shadow-sm"
    } ${isCompact ? "p-2" : "p-4"}`}>
      
      {/* Top Header Controls (if not compact) */}
      {!isCompact && (
        <div className="flex items-center justify-between mb-3 border-b border-white/5 pb-2">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
              {viewMode === "2d" ? "2D Molecule View" : "3D Conformer Explorer"}
            </span>
            <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
              RDKit Deterministic
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setViewMode("2d")}
              className={`px-2 py-1 text-xs rounded transition-all font-medium ${
                viewMode === "2d"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              2D Diagram
            </button>
            <button
              onClick={() => setViewMode("3d")}
              className={`px-2 py-1 text-xs rounded transition-all font-medium flex items-center gap-1 ${
                viewMode === "3d"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              <RotateCw className="w-3 h-3" />
              3D Ball & Stick
            </button>
          </div>
        </div>
      )}

      {/* Main Molecule Visualizer Canvas / SVG */}
      <div 
        className="relative flex items-center justify-center w-full"
        style={{ height: isCompact ? "110px" : "190px" }}
      >
        {viewMode === "2d" ? (
          <svg
            viewBox="0 0 240 180"
            className="w-full h-full select-none"
            style={{ maxHeight: isCompact ? "110px" : "190px" }}
          >
            <defs>
              <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Draw Bonds */}
            {currentMol.bonds.map((bond, i) => {
              const a1 = currentMol.atoms.find((a) => a.id === bond.from);
              const a2 = currentMol.atoms.find((a) => a.id === bond.to);
              if (!a1 || !a2) return null;

              const isDouble = bond.type === "double";
              const isAromatic = bond.type === "aromatic";

              return (
                <g key={`bond-${i}`}>
                  <line
                    x1={a1.x}
                    y1={a1.y}
                    x2={a2.x}
                    y2={a2.y}
                    stroke={theme === "dark" ? "#64748b" : "#475569"}
                    strokeWidth={isCompact ? 2 : 2.5}
                    strokeLinecap="round"
                  />
                  {isDouble && (
                    <line
                      x1={a1.x + 3.5}
                      y1={a1.y + 3.5}
                      x2={a2.x + 3.5}
                      y2={a2.y + 3.5}
                      stroke={theme === "dark" ? "#94a3b8" : "#64748b"}
                      strokeWidth={1.5}
                      strokeLinecap="round"
                    />
                  )}
                  {isAromatic && (
                    <line
                      x1={(a1.x + a2.x) / 2 + 2}
                      y1={(a1.y + a2.y) / 2 + 2}
                      x2={(a1.x + a2.x) / 2 - 2}
                      y2={(a1.y + a2.y) / 2 - 2}
                      stroke="#3b82f6"
                      strokeWidth={1.5}
                      strokeDasharray="2,2"
                    />
                  )}
                </g>
              );
            })}

            {/* Draw Atoms */}
            {currentMol.atoms.map((atom) => {
              const isO = atom.symbol === "O";
              const isN = atom.symbol === "N";
              const isF = atom.symbol === "F";

              let strokeColor = "#64748b";
              let fillColor = theme === "dark" ? "#1e293b" : "#f1f5f9";
              let textColor = theme === "dark" ? "#f8fafc" : "#0f172a";

              if (isO) {
                strokeColor = "#ef4444";
                fillColor = theme === "dark" ? "#450a0a" : "#fee2e2";
                textColor = "#ef4444";
              } else if (isN) {
                strokeColor = "#3b82f6";
                fillColor = theme === "dark" ? "#172554" : "#dbeafe";
                textColor = "#3b82f6";
              } else if (isF) {
                strokeColor = "#10b981";
                fillColor = theme === "dark" ? "#064e3b" : "#d1fae5";
                textColor = "#10b981";
              }

              const radius = isCompact ? 10 : 12;

              return (
                <g
                  key={`atom-${atom.id}`}
                  className="cursor-pointer transition-transform hover:scale-125"
                  onMouseEnter={() => setHoveredAtom(atom)}
                  onMouseLeave={() => setHoveredAtom(null)}
                >
                  <circle
                    cx={atom.x}
                    y={atom.y}
                    r={radius}
                    fill={fillColor}
                    stroke={strokeColor}
                    strokeWidth={isCompact ? 1.5 : 2}
                  />
                  <text
                    x={atom.x}
                    y={atom.y + (isCompact ? 3.5 : 4)}
                    textAnchor="middle"
                    fill={textColor}
                    fontSize={isCompact ? "9" : "11"}
                    fontWeight="700"
                    fontFamily="Inter, sans-serif"
                  >
                    {atom.symbol}
                  </text>
                </g>
              );
            })}
          </svg>
        ) : (
          <div
            className="w-full h-full cursor-grab active:cursor-grabbing"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <canvas
              ref={canvasRef}
              width={260}
              height={180}
              className="w-full h-full"
            />
            <div className="absolute bottom-1 right-2 text-[10px] text-slate-500 font-mono flex items-center gap-1 pointer-events-none">
              <RotateCw className="w-2.5 h-2.5" /> Drag to rotate
            </div>
          </div>
        )}

        {/* Atom Hover Tooltip */}
        {hoveredAtom && !isCompact && (
          <div className="absolute top-2 left-2 bg-slate-900/90 text-white text-[10px] px-2.5 py-1 rounded shadow-lg border border-white/20 backdrop-blur pointer-events-none font-mono">
            Atom #{hoveredAtom.id}: <b>{hoveredAtom.symbol}</b> | {hoveredAtom.hybridization || "sp2"} | Charge: {hoveredAtom.charge || 0}
          </div>
        )}
      </div>

      {/* Bottom Formula / Code (if not compact) */}
      {!isCompact && (
        <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-between text-[11px] text-slate-400 font-mono">
          <span>Formula: <b className="text-slate-200">{currentMol.formula}</b></span>
          <span className="text-emerald-400">Docking: <b>{currentMol.dockingScore}</b></span>
        </div>
      )}
    </div>
  );
}
