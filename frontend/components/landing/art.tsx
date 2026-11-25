import React from "react";

/* Original line-art used across the landing page. All shapes are drawn here, nothing is imported. */

export function LogoMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" aria-hidden="true">
      <path d="M16 3l10 5.8v11.4L16 26 6 20.2V8.8z" />
      <path d="M16 3v9.5M26 8.8l-8.2 4.8M6 8.8l8.2 4.8" opacity=".55" />
      <circle cx="16" cy="14.5" r="2.4" fill="currentColor" stroke="none" />
      <circle cx="16" cy="3" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="26" cy="8.8" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="6" cy="8.8" r="1.6" fill="currentColor" stroke="none" />
    </svg>
  );
}

/* ------------------------------- folder covers ------------------------------- */

interface CoverProps {
  bg: string;
  ink: string;
  title: string;
  children: React.ReactNode;
}

function Cover({ bg, ink, title, children }: CoverProps) {
  const lines = title.split("\n");
  return (
    <div className="fo-folder" aria-hidden="true">
      <div className="fo-folder__tab" style={{ background: bg }} />
      <div className="fo-folder__cover" style={{ background: bg, color: ink }}>
        <svg viewBox="0 0 200 260" width="100%" height="100%" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          {lines.map((l, i) => (
            <text key={i} x="18" y={52 + i * 34} fontSize="31" fontWeight="600" letterSpacing="-1.2" fill="currentColor" stroke="none" style={{ fontFamily: "var(--font-grotesk), sans-serif" }}>
              {l}
            </text>
          ))}
          {children}
          <text x="18" y="244" fontSize="10" fill="currentColor" stroke="none" opacity=".7" style={{ fontFamily: "var(--font-plex), monospace" }}>
            bioresearch
          </text>
        </svg>
      </div>
    </div>
  );
}

export const CoverLiterature = () => (
  <Cover bg="#e3a9a3" ink="#5b1d19" title={"Literature\nsearch"}>
    {[0, 1, 2].flatMap((r) =>
      [0, 1].map((c) => (
        <g key={`${r}${c}`} transform={`translate(${24 + c * 78} ${118 + r * 38})`}>
          <rect width="62" height="30" rx="3" />
          <path d="M8 10h34M8 17h46M8 24h26" opacity=".6" />
        </g>
      ))
    )}
  </Cover>
);

export const CoverBriefing = () => (
  <Cover bg="#a9b49d" ink="#2c3523" title={"Cited\nbriefings"}>
    <rect x="30" y="112" width="120" height="112" rx="4" />
    <path d="M44 134h72M44 148h86M44 162h58M44 176h78M44 190h40" opacity=".65" />
    <circle cx="146" cy="136" r="13" fill="currentColor" opacity=".12" />
    <text x="146" y="141" fontSize="13" textAnchor="middle" fill="currentColor" stroke="none" fontWeight="600">1</text>
    <circle cx="150" cy="196" r="13" fill="currentColor" opacity=".12" />
    <text x="150" y="201" fontSize="13" textAnchor="middle" fill="currentColor" stroke="none" fontWeight="600">2</text>
  </Cover>
);

export const CoverBioactivity = () => (
  <Cover bg="#f0d978" ink="#4a3b05" title={"Bioactivity\ndata"}>
    <path d="M30 222V120M30 222h140" />
    <path d="M30 214C70 214 80 206 100 178S140 128 170 126" strokeWidth="2.4" />
    {[[56, 212], [84, 198], [104, 172], [128, 142], [154, 129]].map(([x, y]) => (
      <circle key={x} cx={x} cy={y} r="4.2" fill="currentColor" />
    ))}
    <path d="M30 150h140" strokeDasharray="3 5" opacity=".5" />
    <text x="172" y="146" fontSize="9" textAnchor="end" fill="currentColor" stroke="none" opacity=".8">IC50</text>
  </Cover>
);

export const CoverCompound = () => (
  <Cover bg="#b3c2da" ink="#1f3150" title={"Compound\nlookup"}>
    {[
      [80, 160],
      [120, 183],
    ].map(([x, y], i) => (
      <path key={i} d={`M${x} ${y - 30}l26 15v30l-26 15-26-15v-30z`} />
    ))}
    <circle cx="80" cy="160" r="9" opacity=".5" />
    <circle cx="106" cy="175" r="9" opacity=".5" />
    <path d="M146 168l22-12M120 213v18" />
    <text x="172" y="156" fontSize="12" fill="currentColor" stroke="none" fontWeight="600">N</text>
    <text x="115" y="238" fontSize="12" fill="currentColor" stroke="none" fontWeight="600">OH</text>
  </Cover>
);

export const CoverTrials = () => (
  <Cover bg="#86c7ca" ink="#0d3a3d" title={"Clinical\ntrials"}>
    <path d="M24 186h152" />
    {[
      [44, "I"],
      [100, "II"],
      [156, "III"],
    ].map(([x, l]) => (
      <g key={l as string}>
        <circle cx={x as number} cy="186" r="15" fill="currentColor" opacity=".12" />
        <circle cx={x as number} cy="186" r="15" />
        <text x={x as number} y="191" fontSize="13" textAnchor="middle" fill="currentColor" stroke="none" fontWeight="600">{l}</text>
      </g>
    ))}
    <path d="M24 134h30l10-18 14 38 12-26 8 6h78" strokeWidth="2.2" />
  </Cover>
);

export const CoverMolecule = () => (
  <Cover bg="#7f95c4" ink="#0e1f4d" title={"Molecule\nviewer"}>
    <path d="M52 200l32-34 40 14 36-40M124 180l8 40" strokeWidth="2.4" />
    {[
      [52, 200, 11],
      [84, 166, 14],
      [124, 180, 12],
      [160, 140, 10],
      [132, 220, 9],
    ].map(([x, y, r], i) => (
      <circle key={i} cx={x} cy={y} r={r} fill="currentColor" opacity={i === 1 ? 0.35 : 0.18} />
    ))}
    {[
      [52, 200, 11],
      [84, 166, 14],
      [124, 180, 12],
      [160, 140, 10],
      [132, 220, 9],
    ].map(([x, y, r], i) => (
      <circle key={`o${i}`} cx={x} cy={y} r={r} />
    ))}
  </Cover>
);

export const CoverAgents = () => (
  <Cover bg="#d2b4e3" ink="#3a1a52" title={"Agent\npipeline"}>
    <circle cx="40" cy="178" r="10" />
    {[130, 178, 226].map((y) => (
      <g key={y}>
        <path d={`M50 178L100 ${y}`} opacity=".6" />
        <circle cx="106" cy={y} r="10" />
        <path d={`M116 ${y}L160 178`} opacity=".6" />
      </g>
    ))}
    <circle cx="170" cy="178" r="10" fill="currentColor" opacity=".25" />
    <circle cx="170" cy="178" r="10" />
  </Cover>
);

export const CoverProperties = () => (
  <Cover bg="#c3c3c3" ink="#2a2a2a" title={"Property\nscreening"}>
    {[1, 0.7, 0.4].map((s, i) => (
      <path key={i} d={pentagon(100, 180, 62 * s)} opacity={0.35 + i * 0.2} />
    ))}
    <path d={pentagon(100, 180, 62 * 0.78, [1, 0.6, 0.9, 0.5, 0.8])} fill="currentColor" opacity=".25" />
  </Cover>
);

function pentagon(cx: number, cy: number, r: number, scale: number[] = [1, 1, 1, 1, 1]) {
  const pts = scale.map((k, i) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / 5;
    return `${(cx + Math.cos(a) * r * k).toFixed(1)} ${(cy + Math.sin(a) * r * k).toFixed(1)}`;
  });
  return `M${pts.join("L")}z`;
}

/* -------------------------------- tile icons -------------------------------- */

const S = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round" } as const;

export const IconSearch = () => (
  <svg viewBox="0 0 140 110" {...S} aria-hidden="true">
    <circle cx="48" cy="46" r="26" />
    <path d="M68 66l22 22" strokeWidth="5" />
    {[24, 40, 56].map((y) => (
      <path key={y} d={`M96 ${y}h36`} opacity=".6" />
    ))}
    <path d="M36 46h24M48 34v24" opacity=".6" />
  </svg>
);
export const IconBriefing = () => (
  <svg viewBox="0 0 140 110" {...S} aria-hidden="true">
    <rect x="30" y="8" width="72" height="94" rx="6" />
    <path d="M42 30h48M42 44h48M42 58h34" opacity=".6" />
    <circle cx="96" cy="78" r="11" />
    <path d="M92 78h8M96 74v8" />
    <path d="M42 82h30" opacity=".6" />
  </svg>
);
export const IconSources = () => (
  <svg viewBox="0 0 140 110" {...S} aria-hidden="true">
    {[0, 1, 2].map((i) => (
      <g key={i} transform={`translate(${i * 14} ${i * -14})`}>
        <rect x="20" y="40" width="70" height="46" rx="5" fill="rgba(255,255,255,.35)" />
        <path d="M30 56h40M30 68h26" opacity=".6" />
      </g>
    ))}
  </svg>
);
export const IconActivity = () => (
  <svg viewBox="0 0 140 110" {...S} aria-hidden="true">
    <rect x="10" y="14" width="120" height="82" rx="8" />
    <path d="M10 32h120" />
    <circle cx="22" cy="23" r="2" />
    <circle cx="31" cy="23" r="2" />
    <path d="M20 70h20l10-22 14 38 12-26 8 10h36" strokeWidth="2.4" />
  </svg>
);
export const IconRefine = () => (
  <svg viewBox="0 0 140 110" {...S} aria-hidden="true">
    <path d="M18 14h104L80 56v34l-20 10V56z" />
    <path d="M40 30h60" opacity=".5" />
  </svg>
);
export const IconMolecule = () => (
  <svg viewBox="0 0 140 110" {...S} aria-hidden="true">
    <path d="M70 12l30 17v34L70 80 40 63V29z" />
    <circle cx="70" cy="46" r="12" opacity=".5" />
    <path d="M100 63l22 12M40 63L18 75M70 80v22" />
    <circle cx="124" cy="76" r="5" />
    <circle cx="16" cy="76" r="5" />
    <circle cx="70" cy="102" r="5" />
  </svg>
);
export const IconListen = () => (
  <svg viewBox="0 0 140 110" {...S} aria-hidden="true">
    <path d="M24 40h22l28-22v74L46 70H24z" />
    <path d="M90 36c10 10 10 28 0 38M104 24c18 18 18 44 0 62" opacity=".7" />
  </svg>
);
export const IconExport = () => (
  <svg viewBox="0 0 140 110" {...S} aria-hidden="true">
    <rect x="30" y="16" width="70" height="86" rx="6" />
    <rect x="48" y="8" width="34" height="16" rx="4" fill="rgba(255,255,255,.4)" />
    <path d="M44 48h42M44 62h30" opacity=".6" />
    <path d="M62 84h40M92 76l10 8-10 8" />
  </svg>
);

export function Arrow({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 8h10M9 4l4 4-4 4" />
    </svg>
  );
}

/* ------------------------------ hero book covers ------------------------------ */
/* Original cover designs: gradients, foil lettering, paper grain, hinge groove and edge light. */

const NOISE = (id: string) => (
  <filter id={id} x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="4" />
    <feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.55 0" />
  </filter>
);

function Finish({ id, light = false }: { id: string; light?: boolean }) {
  return (
    <>
      <rect width="128" height="188" filter={`url(#${id}-n)`} opacity={light ? 0.28 : 0.4} style={{ mixBlendMode: "multiply" }} />
      <rect width="8" height="188" fill={`url(#${id}-spine)`} />
      <rect x="8" width="1.4" height="188" fill="rgba(255,255,255,.28)" />
      <rect x="9.4" width="1" height="188" fill="rgba(0,0,0,.22)" />
      <rect width="128" height="188" fill={`url(#${id}-sheen)`} />
      <rect x=".5" y=".5" width="127" height="187" rx="3" fill="none" stroke="rgba(255,255,255,.18)" />
    </>
  );
}

function Defs({ id, a, b }: { id: string; a: string; b: string }) {
  return (
    <defs>
      <linearGradient id={`${id}-bg`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor={a} />
        <stop offset="1" stopColor={b} />
      </linearGradient>
      <linearGradient id={`${id}-spine`} x1="0" x2="1">
        <stop offset="0" stopColor="rgba(0,0,0,.35)" />
        <stop offset="1" stopColor="rgba(0,0,0,0)" />
      </linearGradient>
      <linearGradient id={`${id}-sheen`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="rgba(255,255,255,.22)" />
        <stop offset=".45" stopColor="rgba(255,255,255,0)" />
        <stop offset="1" stopColor="rgba(0,0,0,.2)" />
      </linearGradient>
      <linearGradient id={`${id}-gold`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#f6e2a6" />
        <stop offset=".5" stopColor="#cfa955" />
        <stop offset="1" stopColor="#8d6c27" />
      </linearGradient>
      {NOISE(`${id}-n`)}
    </defs>
  );
}

/** Deep-green cloth cover with gold-foil serif lettering and a double-helix ornament. */
export const BookGreen = () => {
  const id = "bkg";
  const strand = (phase: number) => {
    let d = "";
    for (let t = 0; t <= 1.001; t += 0.05) {
      const y = 72 + t * 78;
      const x = 64 + Math.sin(t * Math.PI * 3 + phase) * 17;
      d += `${t === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    }
    return d;
  };
  return (
    <svg viewBox="0 0 128 188" width="100%" height="100%" aria-hidden="true">
      <Defs id={id} a="#2d6a4f" b="#0e3023" />
      <rect width="128" height="188" fill={`url(#${id}-bg)`} />
      <rect x="15" y="9" width="104" height="170" fill="none" stroke={`url(#${id}-gold)`} strokeWidth=".7" opacity=".7" />
      <g fill="none" stroke={`url(#${id}-gold)`} strokeLinecap="round">
        {[48, 41, 34].map((r, i) => (
          <circle key={r} cx="64" cy="112" r={r} strokeWidth={i === 0 ? 0.9 : 0.5} opacity={1 - i * 0.22} />
        ))}
        <path d={strand(0)} strokeWidth="1.5" />
        <path d={strand(Math.PI)} strokeWidth="1.5" />
        {Array.from({ length: 11 }, (_, k) => {
          const t = k / 10;
          const y = 72 + t * 78;
          const a = 64 + Math.sin(t * Math.PI * 3) * 17;
          const b = 64 + Math.sin(t * Math.PI * 3 + Math.PI) * 17;
          return <path key={k} d={`M${a.toFixed(1)} ${y.toFixed(1)}L${b.toFixed(1)} ${y.toFixed(1)}`} strokeWidth=".7" opacity=".75" />;
        })}
      </g>
      <g fill={`url(#${id}-gold)`}>
        <text x="64" y="27" textAnchor="middle" fontSize="5.4" letterSpacing="2.2" style={{ fontFamily: "var(--font-grotesk), sans-serif", fontWeight: 600 }}>THE ART OF</text>
        <text x="64" y="52" textAnchor="middle" fontSize="27" fontStyle="italic" style={{ fontFamily: "var(--font-book), Georgia, serif", fontWeight: 600 }}>Drug</text>
        <text x="64" y="68" textAnchor="middle" fontSize="13" letterSpacing=".4" style={{ fontFamily: "var(--font-book), Georgia, serif", fontWeight: 500 }}>Discovery</text>
        <text x="64" y="171" textAnchor="middle" fontSize="4.6" letterSpacing="2" style={{ fontFamily: "var(--font-grotesk), sans-serif", fontWeight: 600 }}>A FIELD GUIDE</text>
      </g>
      <Finish id={id} />
    </svg>
  );
};

/** Burgundy cover with a cream line-art capsule and benzene ring. */
export const BookMaroon = () => {
  const id = "bkm";
  return (
    <svg viewBox="0 0 128 188" width="100%" height="100%" aria-hidden="true">
      <Defs id={id} a="#7a2230" b="#3a0b16" />
      <rect width="128" height="188" fill={`url(#${id}-bg)`} />
      <g fill="none" stroke="#f3e6cf" strokeLinecap="round" strokeLinejoin="round">
        <g transform="rotate(-32 64 96)">
          <rect x="30" y="80" width="68" height="30" rx="15" strokeWidth="1.5" />
          <path d="M64 80v30" strokeWidth="1" />
          <path d="M40 90c4-3 8-3 12 0" strokeWidth=".8" opacity=".6" />
        </g>
        <path d="M86 122l13 7.5v15L86 152l-13-7.5v-15z" strokeWidth="1.4" />
        <circle cx="86" cy="137" r="5.2" strokeWidth=".9" opacity=".8" />
        <path d="M99 144.5l9 5M73 129.5l-8-5" strokeWidth="1.1" />
        <circle cx="64" cy="108" r="58" strokeWidth=".5" opacity=".25" />
        <circle cx="64" cy="108" r="46" strokeWidth=".5" opacity=".25" />
      </g>
      <g fill="#f3e6cf" style={{ fontFamily: "var(--font-grotesk), sans-serif" }}>
        <text x="16" y="25" fontSize="12.5" fontWeight="700" letterSpacing="1.3">MEDICINAL</text>
        <text x="16" y="39" fontSize="12.5" fontWeight="700" letterSpacing="1.3">CHEMISTRY</text>
        <rect x="16" y="45" width="30" height="1.2" />
        <text x="16" y="172" fontSize="4.8" fontWeight="600" letterSpacing="1.6" opacity=".8">FROM HIT TO LEAD</text>
      </g>
      <Finish id={id} />
    </svg>
  );
};

/** Bright paper cover: overlapping translucent squares wired together like a molecular graph. */
export const BookCream = () => {
  const id = "bkc";
  const sq = [
    { x: 24, y: 70, c: "#e8473f" },
    { x: 46, y: 58, c: "#f2b632" },
    { x: 66, y: 76, c: "#2f7cf6" },
    { x: 38, y: 92, c: "#2ab673" },
    { x: 60, y: 100, c: "#9b6ee0" },
  ];
  return (
    <svg viewBox="0 0 128 188" width="100%" height="100%" aria-hidden="true">
      <Defs id={id} a="#fbf8ef" b="#ece6d4" />
      <rect width="128" height="188" fill={`url(#${id}-bg)`} />
      <g style={{ mixBlendMode: "multiply" }}>
        {sq.map((q, i) => (
          <rect key={i} x={q.x} y={q.y + 8} width="38" height="38" fill={q.c} opacity=".88" />
        ))}
      </g>
      <g fill="none" stroke="#25211a" strokeWidth=".8" strokeLinecap="round">
        <path d="M43 85L65 73M65 73L85 91M65 73L57 111M57 111L79 119M57 111L43 105" />
        {[[43, 85], [65, 73], [85, 91], [57, 111], [79, 119], [43, 105]].map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r="2.6" fill="#fbf8ef" />
        ))}
      </g>
      <g fill="#25211a" style={{ fontFamily: "var(--font-grotesk), sans-serif" }}>
        <text x="16" y="24" fontSize="17" fontWeight="700" letterSpacing="-.6">Why Drugs</text>
        <text x="16" y="42" fontSize="17" fontWeight="700" letterSpacing="-.6">Work</text>
        <text x="16" y="166" fontSize="5.2" fontWeight="500" letterSpacing=".5" opacity=".75">how molecules meet</text>
        <text x="16" y="173" fontSize="5.2" fontWeight="500" letterSpacing=".5" opacity=".75">their targets</text>
      </g>
      <Finish id={id} light />
    </svg>
  );
};
