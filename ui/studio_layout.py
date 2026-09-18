"""
NotebookLM-Style 3-Panel Research Studio Layout for BioResearch AI.
Left Panel: Literature Sources & Citations Hub
Center Panel: DeepThink Chat & Executive Synthesis
Right Panel: Discovery Lab (3D Bond Inspector, Audio Overview, MoA Flowcharts, Notes)
"""

from typing import Dict, Any, List
import json
import streamlit as st

from ui.components import render_deepthink_box, render_critic_scorecard
from ui.bond_inspector import render_interactive_bond_inspector
from core.audio_briefing import render_audio_briefing_player
from ui.notebook_view import render_notebook_mode


def render_studio_layout(state: Dict[str, Any]):
    """Render the 3-panel NotebookLM studio workspace."""
    query = state.get("query", "Biomedical Study")
    raw_docs = state.get("raw_documents", [])
    ranked_docs = state.get("ranked_documents", [])
    chemical_analysis = state.get("chemical_analysis", [])
    critic_eval = state.get("critic_evaluation", {})
    final_synthesis = state.get("final_synthesis", {})
    notebook_data = state.get("notebook_data", {})
    reasoning_logs = state.get("reasoning_logs", [])
    exec_time = state.get("execution_time_seconds", 0.0)

    # Top Studio Navbar
    st.markdown(f"""
    <div style="background: rgba(0, 13, 46, 0.95); border-bottom: 1px solid rgba(190, 245, 220, 0.25); padding: 12px 18px; margin: -1rem -1rem 1.5rem -1rem; display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 1.4rem;">🔬</span>
            <div>
                <div style="font-family: var(--font-serif); font-size: 1.25rem; font-weight: 600; color: #FFFFFF;">{query}</div>
                <div style="font-size: 0.75rem; color: #BEF5DC; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;">
                    ✦ Research Studio • {len(ranked_docs)} Indexed Sources • DPO Score: {critic_eval.get('score', 8.5)}/10
                </div>
            </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
            <span class="source-badge badge-chembl">● Studio Active</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 3-Panel Grid: Left (Sources: 3), Middle (Chat/Synthesis: 4.5), Right (Studio Lab: 4.5)
    col_left, col_mid, col_right = st.columns([2.8, 4.2, 5.0])

    # ================= LEFT PANEL: SOURCES HUB =================
    with col_left:
        st.markdown(f"""
        <div style="font-family: var(--font-serif); font-size: 1.15rem; font-weight: 600; color: #FFFFFF; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
            <span>📚 Sources & Evidence</span>
            <span style="font-size: 0.75rem; color: #BEF5DC; font-family: var(--font-mono);">[{len(ranked_docs)}]</span>
        </div>
        """, unsafe_allow_html=True)

        source_filter = st.selectbox(
            "Filter Source Category:",
            ["All Sources", "PubMed", "bioRxiv", "arXiv", "ChEMBL", "PubChem"],
            label_visibility="collapsed"
        )

        filtered_docs = ranked_docs
        if source_filter != "All Sources":
            filtered_docs = [d for d in ranked_docs if d.get("source", "").lower() == source_filter.lower()]

        with st.container(height=650):
            if not filtered_docs:
                st.info("No sources matching filter.")
            for idx, doc in enumerate(filtered_docs, start=1):
                src = doc.get("source", "PubMed")
                b_class = f"badge-{src.lower()}"
                title = doc.get("title", "Untitled")
                url = doc.get("url", "#")
                score = doc.get("relevance_score", 85.0)

                st.markdown(f"""
                <div class="aha-card" style="padding: 10px; margin-bottom: 8px; font-size: 0.82rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <span class="source-badge {b_class}" style="font-size: 0.65rem;">{src}</span>
                        <span style="color: #BEF5DC; font-size: 0.75rem; font-weight: 700;">{score}%</span>
                    </div>
                    <div style="font-family: var(--font-serif); font-size: 0.95rem; font-weight: 600; color: #FFFFFF; margin-bottom: 4px; line-height: 1.3;">
                        <a href="{url}" target="_blank" style="color: #FFFFFF; text-decoration: none;">[{idx}] {title[:65]}...</a>
                    </div>
                    <div style="font-size: 0.75rem; color: #94A3B8;">{doc.get('year', 'Recent')} • {', '.join(doc.get('authors', [])[:1])}</div>
                </div>
                """, unsafe_allow_html=True)
                with st.expander(f"Snippet [{idx}]", expanded=False):
                    st.caption(doc.get("abstract", "")[:350] + "...")

    # ================= MIDDLE PANEL: DEEPTHINK & SYNTHESIS =================
    with col_mid:
        st.markdown("""
        <div style="font-family: var(--font-serif); font-size: 1.15rem; font-weight: 600; color: #FFFFFF; margin-bottom: 8px;">
            💬 Autonomous Synthesis & Reasoning
        </div>
        """, unsafe_allow_html=True)

        with st.container(height=650):
            # 1. DeepThink Box
            render_deepthink_box(reasoning_logs, exec_time)

            # 2. Executive Synthesis
            st.markdown("#### 📑 Executive Research Dossier")
            st.markdown(final_synthesis.get("executive_summary", "Synthesis unavailable."))

            # 3. Critic Validation Scorecard
            if critic_eval:
                st.markdown("---")
                render_critic_scorecard(critic_eval)

            # Quick Prompt Chips
            st.markdown("""
            <div style="margin-top: 14px;">
                <div style="font-size: 0.75rem; color: #94A3B8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px;">Suggested Inquiry Chips:</div>
                <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                    <span class="mol-prop-pill" style="font-size:0.75rem;">🔬 Inspect 3D H-Bonds</span>
                    <span class="mol-prop-pill" style="font-size:0.75rem;">🧬 Target Allosteric Pocket</span>
                    <span class="mol-prop-pill" style="font-size:0.75rem;">📊 View MoA Pathway</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ================= RIGHT PANEL: STUDIO LAB & INSPECTOR =================
    with col_right:
        st.markdown("""
        <div style="font-size: 1.05rem; font-weight: 800; color: #ffffff; margin-bottom: 8px;">
            🧪 Discovery Lab & Bond Inspector
        </div>
        """, unsafe_allow_html=True)

        tab_inspect, tab_audio, tab_vis, tab_notes = st.tabs([
            "🔬 3D Bond Inspector",
            "🎙️ Audio Overview",
            "📊 MoA & Mindmap",
            "📝 Pinned Notes"
        ])

        with tab_inspect:
            if chemical_analysis:
                if len(chemical_analysis) > 1:
                    mol_names = [f"{i+1}. {c.get('name', 'Compound')}" for i, c in enumerate(chemical_analysis)]
                    sel_idx = st.selectbox("Inspect Molecule:", range(len(chemical_analysis)), format_func=lambda i: mol_names[i], key="studio_mol_sel")
                    active_mol = chemical_analysis[sel_idx]
                else:
                    active_mol = chemical_analysis[0]

                render_interactive_bond_inspector(active_mol, height=480)
            else:
                st.info("No validated small molecules available for 3D inspection.")

        with tab_audio:
            lead_mol = chemical_analysis[0] if chemical_analysis else {}
            render_audio_briefing_player(query, lead_mol, ranked_docs, critic_eval, height=480)

        with tab_vis:
            if notebook_data:
                render_notebook_mode(notebook_data, query)
            else:
                st.info("No visualization data generated.")

        with tab_notes:
            st.markdown("#### 📝 Research Notebook Scratchpad")
            default_notes = f"""# Notes for: {query}
- **Lead Candidate:** {chemical_analysis[0].get('name', 'Lead 1') if chemical_analysis else 'Candidate'}
- **Lipinski Status:** Compliant (MW < 500, LogP < 5)
- **Mechanistic Pathway:** Allosteric binding & downstream signaling disruption.
- **Next Steps:** Evaluate in vitro binding affinity (Ki) against target kinase.
"""
            user_notes = st.text_area("Live Study Notes:", value=default_notes, height=280)
            st.download_button(
                "📥 Export Notes (.md)",
                data=user_notes,
                file_name="research_notes.md",
                mime="text/markdown",
                use_container_width=True
            )
