"""
Researcher Agent.
Aggregates literature records, deduplicates findings, extracts biological entities
(genes, target proteins, disease pathways, clinical drug names), and handles DPO revisions.
"""

import re
from typing import Dict, Any, List, Set
from datetime import datetime

from core.state import ResearchState, DocumentModel
from core.llm import LLMClient


# Common biomedical entity patterns and dictionaries
KNOWN_TARGET_PATTERNS = [
    r"\b([A-Z][A-Z0-9]{1,6}(?:-[A-Z0-9]+)?)\b",  # Gene/protein symbols like BACE1, KRAS, EGFR, APP, PSEN1, APOE, LRRK2, TREM2
    r"\b(kinase|secretase|protease|receptor|synthase|phosphatase|polymerase|dehydrogenase|ligase)\b",
    r"\b(beta-amyloid|tau protein|alpha-synuclein|huntingtin|p53|TNF-alpha|IL-6|PD-1|PD-L1|CTLA-4)\b"
]

KNOWN_DRUG_SUFFIXES = (
    "nib", "mab", "ib", "stat", "statin", "sertib", "lisib", "tinib", "parib", "fenib", "rafenib", "ciclib",
    "giline", "pezil", "mine", "vir", "navir", "civir", "lutamide", "degib", "clax", "coxib", "pril", "sartan"
)


class ResearcherAgent:
    """Extracts biological entities and normalizes literature metadata."""

    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient()

    def run(self, state: ResearchState) -> Dict[str, Any]:
        """Execute Researcher agent logic."""
        raw_docs = state.get("raw_documents", [])
        query = state["query"]
        revision_count = state.get("revision_count", 0)
        critic_eval = state.get("critic_evaluation")
        start_ts = datetime.now().strftime("%H:%M:%S")

        logs = list(state.get("reasoning_logs", []))
        
        thought_prefix = ""
        if revision_count > 0 and critic_eval:
            thought_prefix = f"[DPO Loop #{revision_count}] Incorporating Critic guidance: {critic_eval.get('revision_suggestions', [''])[0]}. "

        logs.append({
            "timestamp": start_ts,
            "agent": "Researcher Agent",
            "thought": f"{thought_prefix}Mining {len(raw_docs)} documents for disease pathways, target proteins, and therapeutic candidates.",
            "action": "Running Biomedical Named Entity Extraction (Bio-NER) and metadata alignment.",
            "status": "running"
        })

        # Extract entities from all abstracts and titles
        genes_and_targets: Set[str] = set()
        drug_candidates: Set[str] = set()
        pathways: Set[str] = set()

        for doc_dict in raw_docs:
            text = f"{doc_dict.get('title', '')} {doc_dict.get('abstract', '')}"
            lower_text = text.lower()
            
            # Extract potential target proteins / genes / receptors
            for word in text.split():
                clean_word = word.strip(".,;:()[]{}'\"")
                if len(clean_word) >= 3:
                    # Check uppercase gene / receptor symbols (e.g., HTR1A, 5-HT1A, ADRB1, MAOA, BACE1, KRAS, EGFR, APOE4, GABRA1, DRD2)
                    if (clean_word.isupper() or any(c.isdigit() for c in clean_word)) and any(c.isalpha() for c in clean_word):
                        if len(clean_word) <= 8 and not clean_word.startswith("HTTP"):
                            genes_and_targets.add(clean_word)
                    elif clean_word.lower().endswith(KNOWN_DRUG_SUFFIXES) and len(clean_word) > 4:
                        drug_candidates.add(clean_word.capitalize())

            # Specific Neuropsychiatric / Behavioral pathways (Anger, Aggression, Mood, Stress)
            if "anger" in lower_text or "aggress" in lower_text or "impulsiv" in lower_text:
                pathways.add("Serotonergic & prefrontal-amygdala emotion regulation")
                pathways.add("Autonomic sympathetic arousal & beta-adrenergic signaling")
                genes_and_targets.add("5-HT1A Receptor")
                genes_and_targets.add("5-HT2A Receptor")
                genes_and_targets.add("Beta-1 Adrenergic Receptor")
                genes_and_targets.add("MAO-A (Monoamine Oxidase A)")
                drug_candidates.add("Propranolol")
                drug_candidates.add("Buspirone")
                drug_candidates.add("Fluoxetine")

            if "serotonin" in lower_text or "5-ht" in lower_text:
                pathways.add("Serotonergic neurotransmission & mood regulation")
                genes_and_targets.add("5-HT1A Receptor")
            if "gaba" in lower_text or "inhibitory" in lower_text:
                pathways.add("GABAergic inhibitory interneuron neurotransmission")
                genes_and_targets.add("GABA-A Receptor")
            if "dopamine" in lower_text or "reward" in lower_text:
                pathways.add("Mesolimbic dopaminergic reward & impulse pathway")
                genes_and_targets.add("Dopamine D2 Receptor")
            if "cortisol" in lower_text or "stress" in lower_text or "hpa" in lower_text:
                pathways.add("Hypothalamic-Pituitary-Adrenal (HPA) stress axis")

            # Oncology & Immunology
            if "amyloid" in lower_text:
                pathways.add("Amyloid-beta cascade & plaque deposition")
            if "tau" in lower_text:
                pathways.add("Tau hyperphosphorylation & neurofibrillary tangles")
            if "kras" in lower_text or "mapk" in lower_text:
                pathways.add("MAPK / ERK oncogenic signaling pathway")
            if "pi3k" in lower_text or "akt" in lower_text:
                pathways.add("PI3K / AKT / mTOR survival pathway")

            # Check explicit chemical entities in document
            for chem in doc_dict.get("chemical_entities", []):
                if chem and len(chem) > 2:
                    drug_candidates.add(chem)

        extracted_entities = {
            "genes_and_targets": sorted(list(genes_and_targets))[:12],
            "drug_candidates": sorted(list(drug_candidates))[:12],
            "pathways": sorted(list(pathways))[:8]
        }

        end_ts = datetime.now().strftime("%H:%M:%S")
        logs.append({
            "timestamp": end_ts,
            "agent": "Researcher Agent",
            "thought": f"Identified {len(extracted_entities['genes_and_targets'])} biological targets, {len(extracted_entities['drug_candidates'])} chemical entities, and {len(extracted_entities['pathways'])} disease pathways.",
            "action": "Sending extracted dataset to Re-ranker Agent for cross-encoder semantic prioritization.",
            "status": "completed"
        })

        return {
            "extracted_entities": extracted_entities,
            "reasoning_logs": logs
        }
