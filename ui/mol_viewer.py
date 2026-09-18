"""
3D Molecular Viewer & Bond Inspector Component.
Renders interactive 3D molecular conformers using py3Dmol WebGL,
with style toggles (Stick, Sphere, Surface), Lipinski Rule of 5 badges, and PAINS screening.
"""

from typing import Dict, Any, Optional
import streamlit as st
import streamlit.components.v1 as components


def render_3d_molecule_viewer(
    mol_data: Dict[str, Any],
    height: int = 420,
    viewer_id: str = "mol_viewer"
):
    """Render interactive 3D WebGL molecular viewer and chemical property breakdown."""
    if not mol_data:
        st.warning("No molecular data available to render.")
        return

    name = mol_data.get("name", "Target Molecule")
    smiles = mol_data.get("canonical_smiles") or mol_data.get("smiles", "")
    formula = mol_data.get("molecular_formula", "")
    mw = mol_data.get("mw", 0.0)
    logp = mol_data.get("logp", 0.0)
    hbd = mol_data.get("hbd", 0)
    hba = mol_data.get("hba", 0)
    rot_bonds = mol_data.get("rotatable_bonds", 0)
    tpsa = mol_data.get("tpsa", 0.0)
    passes_ro5 = mol_data.get("passes_lipinski", True)
    has_toxicophore = mol_data.get("has_toxicophore", False)
    pains_alerts = mol_data.get("pains_alerts", [])
    molblock = mol_data.get("conformer_3d_molblock", "")
    mechanism = mol_data.get("mechanism", "Targeted Pathway Modulator")
    rationale = mol_data.get("rationale", "")

    # Header and SMILES
    st.markdown(f"""
    <div style="background: rgba(13, 21, 39, 0.9); border: 1px solid rgba(0, 245, 212, 0.3); border-radius: 12px; padding: 1.2rem; margin-bottom: 1.2rem;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
            <div>
                <div style="font-size: 1.2rem; font-weight: 800; color: #ffffff;">🧬 {name}</div>
                <div style="font-size: 0.85rem; color: #00f5d4; font-family: 'JetBrains Mono', monospace;">Formula: {formula}</div>
            </div>
            <div>
                <span class="mol-prop-pill {'pass' if passes_ro5 else 'fail'}">
                    {'✓ Lipinski Ro5 Passed' if passes_ro5 else '⚠ Ro5 Violations'}
                </span>
                <span class="mol-prop-pill {'pass' if not has_toxicophore else 'fail'}">
                    {'✓ 0 Toxicophores' if not has_toxicophore else '⚠ Toxicophore Alert'}
                </span>
            </div>
        </div>
        <div style="font-size: 0.8rem; color: #9ca3af; font-family: 'JetBrains Mono', monospace; background: rgba(0,0,0,0.4); padding: 6px 10px; border-radius: 6px; word-break: break-all; margin-bottom: 10px;">
            <b>SMILES:</b> {smiles}
        </div>
    """, unsafe_allow_html=True)

    if rationale:
        st.markdown(f"""
        <div style="font-size: 0.85rem; color: #d1d5db; margin-bottom: 10px; line-height: 1.4;">
            <b>Medicinal Chemistry Rationale:</b> {rationale}
        </div>
        """, unsafe_allow_html=True)

    # Lipinski Property Grid
    st.markdown(f"""
        <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; margin-bottom: 14px;">
            <div style="background: rgba(0,0,0,0.3); padding: 6px; border-radius: 6px; text-align: center;">
                <div style="font-size: 0.7rem; color: #9ca3af;">MW (&lt;500)</div>
                <div style="font-size: 0.85rem; font-weight: 700; color: {'#34d399' if mw <= 500 else '#f87171'};">{mw} Da</div>
            </div>
            <div style="background: rgba(0,0,0,0.3); padding: 6px; border-radius: 6px; text-align: center;">
                <div style="font-size: 0.7rem; color: #9ca3af;">LogP (&lt;5.0)</div>
                <div style="font-size: 0.85rem; font-weight: 700; color: {'#34d399' if logp <= 5.0 else '#f87171'};">{logp}</div>
            </div>
            <div style="background: rgba(0,0,0,0.3); padding: 6px; border-radius: 6px; text-align: center;">
                <div style="font-size: 0.7rem; color: #9ca3af;">H-Donors (&lt;5)</div>
                <div style="font-size: 0.85rem; font-weight: 700; color: {'#34d399' if hbd <= 5 else '#f87171'};">{hbd}</div>
            </div>
            <div style="background: rgba(0,0,0,0.3); padding: 6px; border-radius: 6px; text-align: center;">
                <div style="font-size: 0.7rem; color: #9ca3af;">H-Acceptors (&lt;10)</div>
                <div style="font-size: 0.85rem; font-weight: 700; color: {'#34d399' if hba <= 10 else '#f87171'};">{hba}</div>
            </div>
            <div style="background: rgba(0,0,0,0.3); padding: 6px; border-radius: 6px; text-align: center;">
                <div style="font-size: 0.7rem; color: #9ca3af;">Rot. Bonds (&le;10)</div>
                <div style="font-size: 0.85rem; font-weight: 700; color: {'#34d399' if rot_bonds <= 10 else '#f87171'};">{rot_bonds}</div>
            </div>
            <div style="background: rgba(0,0,0,0.3); padding: 6px; border-radius: 6px; text-align: center;">
                <div style="font-size: 0.7rem; color: #9ca3af;">TPSA (&le;140)</div>
                <div style="font-size: 0.85rem; font-weight: 700; color: {'#34d399' if tpsa <= 140 else '#f87171'};">{tpsa} Å²</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if pains_alerts:
        alert_str = ", ".join(pains_alerts)
        st.warning(f"⚠️ Structural Alerts / PAINS detected: {alert_str}")

    # 3D py3Dmol WebGL Viewer HTML
    escaped_molblock = molblock.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/3Dmol/2.4.2/3Dmol-min.js"></script>
        <style>
            body {{
                margin: 0;
                padding: 0;
                background: #080c14;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                color: #e5e7eb;
                overflow: hidden;
            }}
            #container-3d {{
                width: 100%;
                height: {height - 40}px;
                position: relative;
                border-radius: 8px;
                border: 1px solid rgba(0, 245, 212, 0.2);
            }}
            .controls-bar {{
                display: flex;
                gap: 8px;
                padding: 6px 0;
                align-items: center;
            }}
            .control-btn {{
                background: rgba(0, 245, 212, 0.15);
                color: #00f5d4;
                border: 1px solid rgba(0, 245, 212, 0.4);
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 11px;
                cursor: pointer;
                font-weight: 600;
                transition: all 0.2s ease;
            }}
            .control-btn:hover {{
                background: #00f5d4;
                color: #080c14;
            }}
        </style>
    </head>
    <body>
        <div class="controls-bar">
            <span style="font-size: 11px; color: #9ca3af; font-weight: 600;">3D Render Style:</span>
            <button class="control-btn" onclick="setStyle('stick')">Sticks</button>
            <button class="control-btn" onclick="setStyle('sphere')">Spheres</button>
            <button class="control-btn" onclick="setStyle('surface')">Surface</button>
            <button class="control-btn" onclick="toggleSpin()">Toggle Spin</button>
            <button class="control-btn" onclick="resetView()">Reset View</button>
        </div>
        <div id="container-3d"></div>

        <script>
            let viewer = null;
            let spinning = true;
            const molData = `{escaped_molblock}`;

            window.onload = function() {{
                const element = document.getElementById("container-3d");
                const config = {{ backgroundColor: "#080c14" }};
                viewer = $3Dmol.createViewer(element, config);

                if (molData && molData.trim().length > 0) {{
                    viewer.addModel(molData, "mol");
                    viewer.setStyle({{}}, {{
                        stick: {{ radius: 0.18, colorscheme: "cyanCarbon" }},
                        sphere: {{ scale: 0.25, colorscheme: "cyanCarbon" }}
                    }});
                    viewer.zoomTo();
                    viewer.render();
                    viewer.spin("y", 1);
                }} else {{
                    element.innerHTML = "<div style='display:flex;height:100%;align-items:center;justify-content:center;color:#9ca3af;'>No 3D conformer data available</div>";
                }}
            }};

            function setStyle(styleType) {{
                if (!viewer) return;
                viewer.removeAllSurfaces();
                if (styleType === 'stick') {{
                    viewer.setStyle({{}}, {{ stick: {{ radius: 0.2, colorscheme: "cyanCarbon" }} }});
                }} else if (styleType === 'sphere') {{
                    viewer.setStyle({{}}, {{ sphere: {{ scale: 0.5, colorscheme: "cyanCarbon" }} }});
                }} else if (styleType === 'surface') {{
                    viewer.setStyle({{}}, {{ stick: {{ radius: 0.15, colorscheme: "cyanCarbon" }} }});
                    viewer.addSurface($3Dmol.SurfaceType.VDW, {{ opacity: 0.7, color: '#00f5d4' }});
                }}
                viewer.render();
            }}

            function toggleSpin() {{
                if (!viewer) return;
                spinning = !spinning;
                viewer.spin(spinning ? "y" : false, 1);
            }}

            function resetView() {{
                if (!viewer) return;
                viewer.zoomTo();
                viewer.render();
            }}
        </script>
    </body>
    </html>
    """

    components.html(html_code, height=height + 20)
    st.markdown("</div>", unsafe_allow_html=True)
