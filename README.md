<<<<<<< HEAD
# gene
=======
# 🔬 BioResearch AI: Autonomous Biomedical Research Acceleration Platform

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://www.langchain.com/langgraph)
[![RDKit](https://img.shields.io/badge/Cheminformatics-RDKit%202024-green.svg)](https://www.rdkit.org/)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-red.svg)](https://streamlit.io/)

BioResearch AI is an end-to-end autonomous biomedical research platform that orchestrates a team of specialized AI agents using **LangGraph** to replace manual literature review, perform cross-source bioactivity data mining, validate chemical tractability with **RDKit**, enforce a self-correcting **DPO validation loop**, and deliver findings via an interactive, futuristic interface.

---

## 🌟 Key Features

1. **Multi-Source Data Ingestion Factory**:
   - **PubMed / PMC**: NCBI Entrez E-utilities API fetching full abstracts, PMIDs, journal metrics, and authors.
   - **Preprints (bioRxiv / medRxiv)**: Live REST API and RSS feed ingestion.
   - **arXiv**: Quantitative biology (`q-bio`) & bioinformatics algorithms.
   - **ChEMBL**: Bioactivity database pulling target assays, IC50/Ki values, and clinical phases.
   - **PubChem**: PUG REST API resolving compound names to canonical SMILES and molecular properties.
   - **Web Search**: ClinicalTrials.gov & Serper for late-breaking trials and regulatory news.

2. **LangGraph Multi-Agent Team & DPO Self-Correction**:
   - **Router Agent**: Dispatches concurrent multi-source queries.
   - **Researcher Agent**: Performs Bio-NER entity extraction (genes, targets, disease pathways).
   - **Re-ranker Agent**: Scores literature candidates using cross-corpus semantic affinity (Top 10 selection).
   - **Chemist Agent (RDKit)**: Validates Lipinski Rule of 5, Veber rules, screens PAINS/toxicophores, and computes 3D ETKDG conformers.
   - **Critic Agent (DPO Scorer)**: Evaluates biological plausibility and chemical tractability (1-10 scale). Automatically triggers a self-correction revision loop if score < 7.0.
   - **Synthesizer Agent**: Generates structured executive dossiers, citations, and Notebook Mode artifacts.

3. **Interactive UI & Visualizations**:
   - **DeepThink Reasoning Box**: "Thought for X seconds" expandable container tracing real-time internal agent thoughts and actions.
   - **Top 10 Paper Cards**: Interactive cards with source badges, year, relevance percentage, abstract expander, and extracted drug candidates.
   - **3D Molecular Viewer & Bond Inspector**: Embedded py3Dmol WebGL viewer with Stick, Sphere, Surface, and rotation controls.
   - **Notebook Mode**: Interactive Mermaid.js Mechanism of Action (MoA) flowchart and D3.js Hierarchical Research Landscape Mindmap.

---

## 🚀 Quick Start

### 1. Installation
```bash
# Clone the repository
git clone <repo-url>
cd Major_prj

# Create virtual environment and install dependencies
uv venv .venv --python 3.12
uv pip install -r requirements.txt
```

### 2. Run Application
```bash
.venv/bin/streamlit run app.py
```

### 3. Run Tests
```bash
.venv/bin/python -m unittest discover tests
```
>>>>>>> a2073d6e (skeleton done need to reserach some more on the smiles and mole strcutre agent)
