"""
NotebookLM-Style Landing Page & Project Hub for BioResearch AI.
Displays research notebooks, benchmark templates, project stats, and one-click study launchers.
"""

from typing import Callable, List, Dict, Any
import streamlit as st


CURATED_NOTEBOOKS = [
    {
        "id": "nb_alzheimer",
        "title": "Alzheimer's Disease: BACE1 & Amyloid Aggregation Blockers",
        "category": "Neurodegenerative Diseases",
        "description": "Multi-agent literature synthesis exploring dual AChE/BACE1 inhibitors with blood-brain barrier permeability.",
        "icon": "🧠",
        "sources_count": 18,
        "query": "Alzheimer's disease beta-amyloid & BACE1 small molecule inhibitors",
        "lead_drug": "Donepezil-BACE1 Hybrid",
        "dpo_score": 8.7
    },
    {
        "id": "nb_kras",
        "title": "KRAS G12D / G12C Allosteric Pocket Covalent Inhibitors",
        "category": "Targeted Oncology",
        "description": "Targeting the induced switch-II pocket of mutant KRAS oncoproteins in pancreatic and colorectal cancers.",
        "icon": "🧬",
        "sources_count": 22,
        "query": "KRAS G12D allosteric inhibitors in pancreatic ductal adenocarcinoma",
        "lead_drug": "Sotorasib Analog Lead",
        "dpo_score": 9.1
    },
    {
        "id": "nb_egfr",
        "title": "EGFR T790M / C797S Resistance & PROTAC Degraders",
        "category": "Kinase Inhibitors",
        "description": "Overcoming Osimertinib triple-mutation resistance via targeted proteasomal degradation (PROTACs).",
        "icon": "⚡",
        "sources_count": 16,
        "query": "Targeted covalent inhibitors for EGFR T790M / C797S resistance",
        "lead_drug": "Osimertinib-PROTAC Lead",
        "dpo_score": 8.5
    },
    {
        "id": "nb_jak",
        "title": "JAK1 / JAK2 Selective Kinase Modulators in Neuroinflammation",
        "category": "Immunology & CNS",
        "description": "Selective suppression of downstream STAT phosphorylation and microglial neurotoxicity.",
        "icon": "🛡️",
        "sources_count": 14,
        "query": "JAK1/JAK2 selective kinase modulators in autoimmune neuroinflammation",
        "lead_drug": "Baricitinib Derivative",
        "dpo_score": 8.8
    }
]


def render_landing_page(on_select_notebook: Callable[[str], None]):
    """Render the AHA-inspired editorial project hub and landing dashboard."""
    # Hero Section
    st.markdown("""
    <div style="text-align: center; padding: 2.8rem 1rem 1.8rem 1rem;">
        <div class="aha-category-tag">
            ✦ BioResearch AI Studio • Autonomous Literature & Molecular Intelligence
        </div>
        <div class="aha-editorial-title">
            Where Global Science Meets <span>Chemical Precision</span>
        </div>
        <div class="aha-subtitle">
            Autonomous multi-agent intelligence across <b>PubMed, bioRxiv, arXiv, ChEMBL & PubChem</b>.
            Replacing weeks of literature mining with real-time RDKit 3D validation and interactive physiological bond inspection.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Search Bar
    col_s1, col_s2, col_s3 = st.columns([1, 6, 1])
    with col_s2:
        st.markdown("""
        <div style="background: rgba(0, 20, 82, 0.7); border: 1px solid rgba(190, 245, 220, 0.35); border-radius: 12px; padding: 12px 18px; margin-bottom: 2rem; backdrop-filter: blur(12px);">
            <div style="font-size: 0.85rem; color: #BEF5DC; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 4px;">
                🚀 Launch Custom Research Studio:
            </div>
        </div>
        """, unsafe_allow_html=True)

    # AHA Global Stats Counter Bar
    st.markdown("""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; max-width: 1050px; margin: 0 auto 2.5rem auto;">
        <div class="aha-stat-box">
            <div class="aha-stat-num">36M+</div>
            <div class="aha-stat-label">PubMed & PMC Records</div>
        </div>
        <div class="aha-stat-box">
            <div class="aha-stat-num">2.4M</div>
            <div class="aha-stat-label">ChEMBL Bioactivities</div>
        </div>
        <div class="aha-stat-box">
            <div class="aha-stat-num">100%</div>
            <div class="aha-stat-label">RDKit Physical Validation</div>
        </div>
        <div class="aha-stat-box">
            <div class="aha-stat-num">8.8/10</div>
            <div class="aha-stat-label">DPO Critic Quality Gate</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Notebook Grid Title
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.2rem; border-bottom: 1px solid rgba(190, 245, 220, 0.2); padding-bottom: 0.6rem;">
        <div style="font-family: var(--font-serif); font-size: 1.6rem; font-weight: 600; color: #FFFFFF;">
            Featured Benchmark Research Notebooks
        </div>
        <div style="font-size: 0.82rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em;">
            Select any study to open the 3-Panel Studio
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Notebook Cards (2 Columns)
    col_left, col_right = st.columns(2)

    for i, nb in enumerate(CURATED_NOTEBOOKS):
        target_col = col_left if i % 2 == 0 else col_right
        with target_col:
            st.markdown(f"""
            <div class="aha-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                    <span style="font-size: 2.2rem;">{nb['icon']}</span>
                    <span class="source-badge badge-chembl">DPO Score: {nb['dpo_score']}/10</span>
                </div>
                <div style="font-family: var(--font-serif); font-size: 1.3rem; font-weight: 600; color: #FFFFFF; margin-bottom: 4px; line-height: 1.25;">
                    {nb['title']}
                </div>
                <div style="font-size: 0.75rem; color: #BEF5DC; text-transform: uppercase; font-weight: 700; letter-spacing: 0.1em; margin-bottom: 8px;">
                    {nb['category']} • {nb['sources_count']} Indexed Sources
                </div>
                <div style="font-size: 0.88rem; color: #CBD5E1; line-height: 1.5; margin-bottom: 14px;">
                    {nb['description']}
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="mol-prop-pill pass">💊 {nb['lead_drug']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"⚡ Open Study: {nb['title'][:26]}...", key=f"btn_nb_{nb['id']}", use_container_width=True):
                on_select_notebook(nb['query'])
