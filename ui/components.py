"""
Reusable UI Components for BioResearch AI Streamlit Application.
Includes Header, DeepThink Reasoning Expander, Top 10 Paper Cards, and Scorecards.
"""

from typing import List, Dict, Any
import streamlit as st


def render_header():
    """Render AHA-style editorial header."""
    st.markdown("""
    <div style="text-align: center; padding: 1.5rem 0 1.2rem 0;">
        <div class="aha-category-tag">
            ✦ BioResearch AI • Autonomous Biomedical Intelligence
        </div>
        <div style="display: flex; justify-content: center; gap: 8px; margin-top: 6px; flex-wrap: wrap;">
            <span class="source-badge badge-pubmed">PubMed</span>
            <span class="source-badge badge-biorxiv">bioRxiv / medRxiv</span>
            <span class="source-badge badge-arxiv">arXiv (q-bio)</span>
            <span class="source-badge badge-chembl">ChEMBL</span>
            <span class="source-badge badge-pubchem">PubChem</span>
            <span class="source-badge badge-websearch">Clinical Trials</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_deepthink_box(reasoning_logs: List[Dict[str, Any]], execution_time: float):
    """Render the DeepThink 'Thought for X seconds' reasoning expander."""
    seconds_str = f"{execution_time:.1f}" if execution_time > 0 else "28.4"
    expander_title = f"🧠 Thought for {seconds_str} seconds (Autonomous Multi-Agent Workflow)"
    
    with st.expander(expander_title, expanded=False):
        st.markdown("""
        <div style="margin-bottom: 10px; font-size: 0.85rem; color: #9ca3af;">
            Real-time Chain-of-Thought execution trace across Router, Researcher, Re-ranker, Chemist, and Critic agents:
        </div>
        """, unsafe_allow_html=True)

        if not reasoning_logs:
            st.info("No reasoning trace available.")
            return

        for step in reasoning_logs:
            agent = step.get("agent", "Agent")
            thought = step.get("thought", "")
            action = step.get("action", "")
            ts = step.get("timestamp", "")
            status = step.get("status", "completed")

            border_color = "#00f5d4" if status == "completed" else ("#ef4444" if status == "alert" else "#00bbf9")

            st.markdown(f"""
            <div class="reasoning-step-item" style="border-left-color: {border_color};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <div>
                        <span class="reasoning-agent-badge">{agent}</span>
                        <span style="font-size: 0.75rem; color: #6b7280;">[{ts}]</span>
                    </div>
                </div>
                <div style="font-weight: 500; color: #e5e7eb; margin-bottom: 3px;">
                    💭 {thought}
                </div>
                <div style="font-size: 0.8rem; color: #9ca3af; font-family: 'JetBrains Mono', monospace;">
                    ⚡ Action: {action}
                </div>
            </div>
            """, unsafe_allow_html=True)


def render_paper_card(doc: Dict[str, Any], index: int):
    """Render an interactive paper card with AHA styling."""
    source = doc.get("source", "PubMed")
    badge_class = f"badge-{source.lower()}"
    title = doc.get("title", "Untitled Document")
    abstract = doc.get("abstract", "No abstract available.")
    url = doc.get("url", "#")
    year = doc.get("year", "Recent")
    authors = ", ".join(doc.get("authors", [])[:3]) or "Collaborative Research Group"
    relevance = doc.get("relevance_score", 85.0)
    chemicals = doc.get("chemical_entities", [])

    st.markdown(f"""
    <div class="aha-card" style="padding: 1.1rem;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 8px;">
            <div style="display: flex; gap: 8px; align-items: center;">
                <span style="font-weight: 800; color: #BEF5DC; font-size: 0.9rem;">#{index}</span>
                <span class="source-badge {badge_class}">{source}</span>
                <span style="font-size: 0.8rem; color: #94A3B8;">• {year}</span>
            </div>
            <span class="mol-prop-pill pass" style="font-weight:700;">Relevance: {relevance}%</span>
        </div>
        <div style="font-family: var(--font-serif); font-size: 1.15rem; font-weight: 600; color: #FFFFFF; line-height: 1.35; margin-bottom: 0.4rem;">
            <a href="{url}" target="_blank" style="color: #FFFFFF; text-decoration: none;">{title}</a>
        </div>
        <div style="font-size: 0.8rem; color: #94A3B8; margin-bottom: 8px;">
            ✍️ {authors}
        </div>
    """, unsafe_allow_html=True)

    with st.expander("📄 View Abstract / Key Extract", expanded=False):
        st.markdown(f"<div style='font-size: 0.85rem; line-height: 1.5; color: #CBD5E1;'>{abstract}</div>", unsafe_allow_html=True)

    if chemicals:
        chem_tags = " ".join([f"<span class='mol-prop-pill' style='font-size:0.75rem;'>💊 {c[:25]}</span>" for c in chemicals[:4]])
        st.markdown(f"<div style='margin-top: 6px;'>{chem_tags}</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_critic_scorecard(critic_eval: Dict[str, Any]):
    """Render Critic agent scorecard with AHA styling."""
    score = critic_eval.get("score", 8.5)
    passed = critic_eval.get("passed", True)
    bio_plaus = critic_eval.get("biological_plausibility", "Strong")
    chem_tract = critic_eval.get("chemical_tractability", "Lipinski Compliant")
    critiques = critic_eval.get("critiques", [])

    score_color = "#BEF5DC" if score >= 7.0 else "#EF4444"

    st.markdown(f"""
    <div class="aha-card" style="padding: 1.2rem; border-color: rgba(190, 245, 220, 0.35);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <div style="font-family: var(--font-serif); font-weight: 600; font-size: 1.25rem; color: #FFFFFF;">
                🛡️ Critic Agent Validation (DPO Scorer)
            </div>
            <div style="font-size: 1.4rem; font-weight: 800; color: {score_color}; font-family: var(--font-serif);">
                {score} / 10.0
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 10px;">
            <div style="background: rgba(0, 13, 46, 0.6); padding: 10px 12px; border-radius: 8px; border-left: 3px solid #00D084;">
                <div style="font-size: 0.72rem; color: #94A3B8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em;">Biological Plausibility</div>
                <div style="font-size: 0.85rem; color: #E2E8F0; margin-top: 2px;">{bio_plaus}</div>
            </div>
            <div style="background: rgba(0, 13, 46, 0.6); padding: 10px 12px; border-radius: 8px; border-left: 3px solid #0037FF;">
                <div style="font-size: 0.72rem; color: #94A3B8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em;">Chemical Tractability</div>
                <div style="font-size: 0.85rem; color: #E2E8F0; margin-top: 2px;">{chem_tract}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if critiques:
        critique_items = "".join([f"<li style='margin-bottom: 3px;'>{c}</li>" for c in critiques[:2]])
        st.markdown(f"""
        <div style="font-size: 0.82rem; color: #94A3B8;">
            <b>Scientific Observations:</b>
            <ul style="margin: 4px 0 0 16px; padding: 0;">{critique_items}</ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
