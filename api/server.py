"""
BioResearch AI - High-Performance FastAPI Backend Server.
Connects Next.js Frontend with Python LangGraph Multi-Agent Engine & RDKit 3D Cheminformatics.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.workflow import BioResearchWorkflow
from ui.bond_inspector import extract_photorealistic_graph_details
from ui.landing_page import CURATED_NOTEBOOKS
import config

app = FastAPI(
    title="BioResearch AI API",
    description="Backend API for Autonomous Biomedical Literature Mining & 3D Cheminformatics",
    version="2.0.0"
)

# Enable CORS for Next.js (port 3000 / any localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton workflow instance
workflow_instance = BioResearchWorkflow()


class ResearchRequest(BaseModel):
    query: str
    focus_target: Optional[str] = None


class MoleculeInspectRequest(BaseModel):
    smiles: str
    name: Optional[str] = "Candidate Molecule"


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "platform": "BioResearch AI Next.js Edition",
        "engines": {
            "langgraph": True,
            "rdkit": True,
            "pubmed_api": True,
            "biorxiv_api": True,
            "chembl_api": True,
            "pubchem_api": True
        }
    }


@app.get("/api/presets")
def get_presets():
    """Return curated benchmark notebooks."""
    return {"presets": CURATED_NOTEBOOKS}


@app.post("/api/research")
def run_research_pipeline(req: ResearchRequest):
    """Execute LangGraph autonomous multi-agent pipeline."""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        result_state = workflow_instance.run(req.query.strip(), focus_target=req.focus_target)
        return {
            "success": True,
            "state": result_state
        }
    except Exception as e:
        print(f"[API Error] Research execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/inspect-molecule")
def inspect_molecule(req: MoleculeInspectRequest):
    """Compute detailed 3D coordinates, bond lengths, and physiological body effects."""
    if not req.smiles or not req.smiles.strip():
        raise HTTPException(status_code=400, detail="SMILES string required.")

    try:
        details = extract_photorealistic_graph_details(req.smiles.strip())
        if not details:
            raise HTTPException(status_code=422, detail="Invalid SMILES structure.")
        return {
            "success": True,
            "name": req.name,
            "smiles": req.smiles,
            "details": details
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
