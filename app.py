"""
BioResearch AI - Autonomous Biomedical Research & Drug Discovery Platform.
Main Application Entry Point featuring NotebookLM-Style SaaS Architecture.
"""

import os
import sys
from pathlib import Path
import streamlit as st

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from core.workflow import BioResearchWorkflow
from ui.landing_page import render_landing_page
from ui.studio_layout import render_studio_layout
from ui.components import render_header


# Streamlit Page Configuration
st.set_page_config(
    page_title="BioResearch AI | Autonomous Drug Discovery Studio",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load Custom CSS Styling
css_path = Path(__file__).parent / "ui" / "styles.css"
if css_path.exists():
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def init_session_state():
    """Initialize Streamlit session state variables."""
    if "research_state" not in st.session_state:
        st.session_state.research_state = None
    if "workflow" not in st.session_state:
        st.session_state.workflow = BioResearchWorkflow()
    if "current_view" not in st.session_state:
        st.session_state.current_view = "landing"  # "landing" or "studio"
    if "active_query" not in st.session_state:
        st.session_state.active_query = "Alzheimer's disease beta-amyloid & BACE1 small molecule inhibitors"


def run_research(query_text: str):
    """Execute multi-agent workflow and switch to Studio view."""
    with st.status(f"🧬 Launching BioResearch Autonomous Team for '{query_text[:40]}...'...", expanded=True) as status:
        st.write("🛰️ **Router Agent:** Dispatched concurrent scrapers to PubMed, bioRxiv, arXiv, ChEMBL, PubChem, ClinicalTrials...")
        st.write("🔬 **Researcher Agent:** Extracting targets, disease pathways, and candidate entities...")
        st.write("📊 **Re-ranker Agent:** Cross-encoder scoring and selecting Top 10 publications...")
        st.write("🧪 **Chemist Agent (RDKit):** Calculating Lipinski properties, 3D conformers, and toxicophore screening...")
        st.write("🛡️ **Critic Agent:** Running DPO quality validation loop...")
        st.write("📑 **Synthesizer Agent:** Compiling executive dossier, 3D bond matrix, audio overview, and Mermaid MoA...")
        
        try:
            state_result = st.session_state.workflow.run(query_text.strip())
            st.session_state.research_state = state_result
            st.session_state.active_query = query_text
            st.session_state.current_view = "studio"
            status.update(label="✅ Autonomous Research Complete! Loading Studio...", state="complete", expanded=False)
            st.rerun()
        except Exception as e:
            st.error(f"Execution Error: {e}")
            status.update(label="❌ Execution Encountered an Issue", state="error")


def render_sidebar():
    """Render sidebar navigation, quick presets, and API settings."""
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 1.2rem;">
            <div style="font-size: 1.3rem; font-weight: 800; color: #00f5d4;">🔬 BioResearch Studio</div>
            <div style="font-size: 0.75rem; color: #9ca3af;">Autonomous Drug Discovery SaaS</div>
        </div>
        """, unsafe_allow_html=True)

        # View Navigation
        st.markdown("### 🧭 Workspace View")
        view_choice = st.radio(
            "Select View:",
            ["🏠 Notebooks Hub (Landing)", "🔬 Active Research Studio"],
            index=0 if st.session_state.current_view == "landing" else 1,
            label_visibility="collapsed"
        )
        if view_choice == "🏠 Notebooks Hub (Landing)" and st.session_state.current_view != "landing":
            st.session_state.current_view = "landing"
            st.rerun()
        elif view_choice == "🔬 Active Research Studio" and st.session_state.current_view != "studio":
            if st.session_state.research_state:
                st.session_state.current_view = "studio"
                st.rerun()
            else:
                st.info("Run or select a research notebook first to open the Studio.")

        st.markdown("---")
        st.markdown("### 🎯 Quick Study Presets")
        presets = [
            "Alzheimer's disease beta-amyloid & BACE1 small molecule inhibitors",
            "KRAS G12D allosteric inhibitors in pancreatic ductal adenocarcinoma",
            "Targeted covalent inhibitors for EGFR T790M / C797S resistance",
            "PROTAC degraders for Tau protein hyperphosphorylation in dementia",
            "JAK1/JAK2 selective kinase modulators in autoimmune neuroinflammation"
        ]
        for p in presets:
            if st.button(f"⚡ {p[:32]}...", key=f"side_p_{p[:10]}", use_container_width=True):
                run_research(p)

        st.markdown("---")
        st.markdown("### 🤖 Intelligence Engine")
        llm_provider = st.selectbox(
            "Model Provider:",
            ["Auto (Gemini / OpenAI / Fallback)", "Google Gemini", "OpenAI GPT-4o", "Heuristic Engine"],
            index=0
        )
        gemini_key = st.text_input("Gemini API Key (Optional):", type="password", value=config.GOOGLE_API_KEY)
        if gemini_key and gemini_key != config.GOOGLE_API_KEY:
            config.GOOGLE_API_KEY = gemini_key

        openai_key = st.text_input("OpenAI API Key (Optional):", type="password", value=config.OPENAI_API_KEY)
        if openai_key and openai_key != config.OPENAI_API_KEY:
            config.OPENAI_API_KEY = openai_key

        st.markdown("---")
        st.markdown("""
        <div style="font-size: 0.75rem; line-height: 1.6; color: #9ca3af;">
            🟢 <b>PubMed:</b> NCBI E-utilities<br/>
            🟢 <b>Preprints:</b> bioRxiv/medRxiv REST<br/>
            🟢 <b>ChEMBL:</b> Bioactivity API<br/>
            🟢 <b>PubChem:</b> PUG REST Resolver<br/>
            🟢 <b>RDKit:</b> 3D Conformer & Bond Inspector
        </div>
        """, unsafe_allow_html=True)


def main():
    """Main application loop."""
    init_session_state()
    render_sidebar()

    if st.session_state.current_view == "landing":
        # 1. Top Search Bar for immediate query input
        col1, col2, col3 = st.columns([1, 6, 1])
        with col2:
            query_input = st.text_input(
                "Search or create a new research notebook:",
                value="",
                placeholder="e.g. Alzheimer's disease beta-amyloid & BACE1 small molecule inhibitors...",
                label_visibility="collapsed"
            )
            col_b1, col_b2 = st.columns([4, 2])
            with col_b2:
                if st.button("🚀 Start Research Studio", type="primary", use_container_width=True):
                    target_q = query_input.strip() if query_input.strip() else st.session_state.active_query
                    run_research(target_q)

        # 2. Render NotebookLM Landing Page
        render_landing_page(on_select_notebook=run_research)

    elif st.session_state.current_view == "studio":
        # Render 3-Panel Studio Layout
        if st.session_state.research_state:
            # Back Button
            if st.button("← Back to All Notebooks Hub"):
                st.session_state.current_view = "landing"
                st.rerun()

            render_studio_layout(st.session_state.research_state)
        else:
            st.info("No active research notebook. Please select or launch a study.")
            if st.button("Go to Notebooks Hub"):
                st.session_state.current_view = "landing"
                st.rerun()


if __name__ == "__main__":
    main()
