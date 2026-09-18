"""
State definitions for BioResearch AI LangGraph Workflow.
"""

from typing import List, Dict, Any, Optional, TypedDict
from pydantic import BaseModel, Field


class DocumentModel(BaseModel):
    """Normalized document schema across all 6 data ingestion sources."""
    id: str = Field(default="", description="Unique identifier or PMID/DOI")
    title: str = Field(description="Title of research paper or entry")
    abstract: str = Field(default="", description="Abstract or full text snippet")
    source: str = Field(description="PubMed, bioRxiv, arXiv, ChEMBL, PubChem, WebSearch")
    url: str = Field(default="", description="URL to open paper or database entry")
    year: str = Field(default="Recent", description="Publication year")
    authors: List[str] = Field(default_factory=list, description="Authors list")
    doi: Optional[str] = None
    pmid: Optional[str] = None
    chemical_entities: List[str] = Field(default_factory=list, description="Extracted drugs/molecules")
    bioactivity_data: Dict[str, Any] = Field(default_factory=dict, description="IC50, Ki, assay targets")
    relevance_score: float = Field(default=0.0, description="Cross-encoder relevance score (0-100)")


class ChemicalCandidate(BaseModel):
    """Extracted or synthesized chemical entity with RDKit validation."""
    name: str
    smiles: str
    canonical_smiles: Optional[str] = None
    molecular_formula: Optional[str] = None
    mw: float = 0.0
    logp: float = 0.0
    hbd: int = 0
    hba: int = 0
    rotatable_bonds: int = 0
    tpsa: float = 0.0
    passes_lipinski: bool = False
    pains_alerts: List[str] = Field(default_factory=list)
    has_toxicophore: bool = False
    conformer_3d_molblock: Optional[str] = None
    mechanism: Optional[str] = None
    rationale: Optional[str] = None
    source_citation: Optional[str] = None


class CriticEvaluation(BaseModel):
    """Evaluation output from Critic agent."""
    score: float = Field(description="Score between 1.0 and 10.0")
    passed: bool = Field(description="True if score >= 7.0")
    biological_plausibility: str = Field(default="")
    chemical_tractability: str = Field(default="")
    literature_grounding: str = Field(default="")
    critiques: List[str] = Field(default_factory=list)
    revision_suggestions: List[str] = Field(default_factory=list)


class ReasoningStep(BaseModel):
    """Step in Chain-of-Thought reasoning for DeepThink UI."""
    timestamp: str
    agent: str
    thought: str
    action: str
    status: str = "completed"  # running, completed, alert


class ResearchState(TypedDict):
    """LangGraph multi-agent shared state dictionary."""
    query: str
    focus_target: Optional[str]
    raw_documents: List[Dict[str, Any]]
    ranked_documents: List[Dict[str, Any]]
    extracted_entities: Dict[str, Any]
    chemical_analysis: List[Dict[str, Any]]
    critic_evaluation: Optional[Dict[str, Any]]
    revision_count: int
    max_revisions: int
    reasoning_logs: List[Dict[str, Any]]
    final_synthesis: Optional[Dict[str, Any]]
    notebook_data: Optional[Dict[str, Any]]
    execution_time_seconds: float
