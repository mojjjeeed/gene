/**
 * Fixture data for the research dossier (sample content only - not retrieved from any live source).
 * Moved verbatim out of app/api/research/route.ts so it can sit behind the same interface the live
 * implementation uses (lib/surfaces/research.ts).
 */
import type { CitationItem, ResearchResponse } from "@/lib/research";

export function buildDemoDossier(query: string): Omit<ResearchResponse, "execution_time_seconds" | "data_source"> {
  const q = query.toLowerCase();
  let papers: CitationItem[];

  if (q.includes("egfr") || q.includes("kinase") || q.includes("osimertinib")) {
    papers = [
      {
        citation_index: 1,
        id: "demo_egfr_1",
        title: "Sample: Allosteric Kinase Modulation in EGFR T790M/C797S Resistance",
        source: "PubMed",
        authors: ["Sample Author A.", "Sample Author B."],
        year: "2024",
        url: "https://pubmed.ncbi.nlm.nih.gov/?term=EGFR+T790M+C797S",
        abstract:
          "Sample abstract: reversible and allosteric EGFR inhibitors that address osimertinib triple-mutation resistance in non-small cell lung cancer.",
        evidence_quote: "Allosteric kinase inhibition showed selectivity over wild-type EGFR in this sample dataset.",
      },
      {
        citation_index: 2,
        id: "demo_egfr_2",
        title: "Sample: Structural Characterisation of Mutant EGFR",
        source: "bioRxiv",
        authors: ["Sample Author C."],
        year: "2024",
        url: "https://www.biorxiv.org/search/EGFR",
        abstract: "Sample abstract: structural analysis of an induced allosteric pocket adjacent to the hinge region.",
        evidence_quote: "Density maps in this sample suggest a conserved water network near the binding site.",
      },
      {
        citation_index: 3,
        id: "demo_egfr_3",
        title: "Sample: Kinase Panel Bioactivity Profile",
        source: "ChEMBL",
        authors: ["EMBL-EBI ChEMBL"],
        year: "2024",
        url: "https://www.ebi.ac.uk/chembl/",
        abstract: "Sample abstract: assay measurements across a kinase panel.",
        evidence_quote: "Selectivity against off-target kinases is summarised in this sample record.",
      },
    ];
  } else if (q.includes("kras") || q.includes("g12d") || q.includes("pancrea")) {
    papers = [
      {
        citation_index: 1,
        id: "demo_kras_1",
        title: "Sample: Switch-II Pocket Targeting in KRAS G12D",
        source: "PubMed",
        authors: ["Sample Author A."],
        year: "2024",
        url: "https://pubmed.ncbi.nlm.nih.gov/?term=KRAS+G12D",
        abstract: "Sample abstract: switch-II pocket ligands that disrupt effector interaction in pancreatic adenocarcinoma.",
        evidence_quote: "Binding to the induced switch-II cavity reduced downstream MAPK signalling in this sample.",
      },
      {
        citation_index: 2,
        id: "demo_kras_2",
        title: "Sample: Binding Kinetics of Reversible G12D Ligands",
        source: "ChEMBL",
        authors: ["Sample Author B."],
        year: "2024",
        url: "https://www.ebi.ac.uk/chembl/",
        abstract: "Sample abstract: surface plasmon resonance data and cellular target engagement.",
        evidence_quote: "Binding kinetics are summarised in this sample record.",
      },
    ];
  } else {
    papers = [
      {
        citation_index: 1,
        id: "demo_generic_1",
        title: `Sample: Target Validation and Therapeutic Advances in ${query}`,
        source: "PubMed",
        authors: ["Sample Author A."],
        year: "2024",
        url: `https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(query)}`,
        abstract: `Sample abstract: receptor engagement and cellular pharmacodynamics in ${query}.`,
        evidence_quote: `Sample evidence statement about target engagement in ${query}.`,
      },
      {
        citation_index: 2,
        id: "demo_generic_2",
        title: `Sample: Biomarker Screening and Pharmacokinetics for ${query}`,
        source: "bioRxiv",
        authors: ["Sample Author B."],
        year: "2024",
        url: `https://www.biorxiv.org/search/${encodeURIComponent(query)}`,
        abstract: "Sample abstract: selectivity over off-target isoforms and metabolic clearance.",
        evidence_quote: "Sample evidence statement about selectivity and clearance.",
      },
    ];
  }

  const c1 = `[${papers[0].citation_index}]`;
  const c2 = `[${(papers[1] ?? papers[0]).citation_index}]`;
  const c3 = `[${(papers[2] ?? papers[1] ?? papers[0]).citation_index}]`;

  return {
    success: true,
    query,
    notebook_data: {
      sections: [
        {
          id: "executive_summary",
          title: "Executive Summary (sample)",
          content: `This is a **sample briefing** shown because the research backend is offline. Real results for **${query}** will replace it once the backend is running. Sample themes: precision target modulation ${c1}, pathway restoration ${c2}, and selectivity windows ${c3}.`,
        },
        {
          id: "key_findings",
          title: "Key Findings (sample)",
          content: `- **Target engagement:** placeholder statement about binding and selectivity ${c1}.\n- **Signalling:** placeholder statement about pathway modulation ${c2}.\n- **Pharmacology:** placeholder statement about clearance and safety ${c3}.`,
        },
      ],
      citations: papers,
      source_count: papers.length,
    },
    ranked_documents: papers,
    reasoning_logs: [
      {
        timestamp: new Date().toLocaleTimeString("en-GB"),
        agent: "Frontend Gateway",
        thought: "The research backend could not be reached, so built-in sample content was returned.",
        action: "Start the FastAPI server (port 8000) to retrieve live literature.",
        status: "fallback",
      },
    ],
  };
}
