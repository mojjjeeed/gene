"""
Notebook Mode Component for BioResearch AI.
Renders Mermaid.js Mechanism of Action (MoA) Flowcharts and Hierarchical Research Landscape Mindmaps.
"""

from typing import Dict, Any
import json
import streamlit as st
import streamlit.components.v1 as components


def render_notebook_mode(notebook_data: Dict[str, Any], query: str):
    """Render interactive Flowchart, Mindmap, and Research Dossier Notebook."""
    if not notebook_data:
        st.info("No Notebook Mode data generated yet.")
        return

    mermaid_code = notebook_data.get("mermaid_flowchart", "")
    mindmap_data = notebook_data.get("mindmap_tree", {})

    st.markdown("""
    <div style="background: rgba(13, 21, 39, 0.8); border: 1px solid rgba(0, 245, 212, 0.25); border-radius: 12px; padding: 1.2rem; margin-bottom: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <div style="font-size: 1.3rem; font-weight: 800; color: #ffffff;">
                📓 Research Notebook & Systems Biology Engine
            </div>
            <span class="source-badge badge-chembl">Interactive Visuals</span>
        </div>
        <div style="font-size: 0.85rem; color: #9ca3af;">
            Visualizing target disease mechanisms, allosteric pathways, and multi-dimensional research trees.
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📊 Mechanism Flowchart (Mermaid.js)", "🧠 Research Mindmap", "📥 Export Full Dossier"])

    with tab1:
        st.markdown("#### Disease Mechanism of Action (MoA) Pathway")
        st.markdown("<p style='font-size: 0.85rem; color: #9ca3af;'>Interactive DAG tracing pathological triggers, target engagement, and therapeutic rescue:</p>", unsafe_allow_html=True)

        escaped_mermaid = mermaid_code.replace("`", "\\`").replace("$", "\\$")
        mermaid_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
            <style>
                body {{
                    background-color: #080c14;
                    color: #e5e7eb;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    padding: 10px;
                    margin: 0;
                }}
                .mermaid {{
                    width: 100%;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="mermaid">
{escaped_mermaid}
            </div>
            <script>
                mermaid.initialize({{
                    startOnLoad: true,
                    theme: 'dark',
                    themeVariables: {{
                        darkMode: true,
                        background: '#080c14',
                        primaryColor: '#7928ca',
                        primaryTextColor: '#ffffff',
                        primaryBorderColor: '#00f5d4',
                        lineColor: '#00f5d4',
                        secondaryColor: '#00bbf9',
                        tertiaryColor: '#10b981'
                    }}
                }});
            </script>
        </body>
        </html>
        """
        components.html(mermaid_html, height=450, scrolling=True)

    with tab2:
        st.markdown("#### Hierarchical Research Landscape Mindmap")
        st.markdown("<p style='font-size: 0.85rem; color: #9ca3af;'>Structured taxonomy: Pathology &rarr; Biological Targets &rarr; Lead Compounds &rarr; Evidence Base</p>", unsafe_allow_html=True)

        mindmap_json_str = json.dumps(mindmap_data)
        escaped_json = mindmap_json_str.replace("`", "\\`").replace("$", "\\$")

        d3_mindmap_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="https://d3js.org/d3.v7.min.js"></script>
            <style>
                body {{
                    background: #080c14;
                    color: #e5e7eb;
                    font-family: 'Plus Jakarta Sans', sans-serif, system-ui;
                    margin: 0;
                    overflow-x: auto;
                }}
                .node circle {{
                    fill: #00f5d4;
                    stroke: #080c14;
                    stroke-width: 2px;
                }}
                .node text {{
                    font-size: 11px;
                    fill: #f3f4f6;
                    font-family: 'JetBrains Mono', monospace;
                }}
                .link {{
                    fill: none;
                    stroke: rgba(0, 245, 212, 0.3);
                    stroke-width: 1.5px;
                }}
            </style>
        </head>
        <body>
            <div id="mindmap-container" style="width: 100%; height: 480px;"></div>

            <script>
                const data = {escaped_json};
                const width = 800;
                const height = 480;

                const svg = d3.select("#mindmap-container")
                    .append("svg")
                    .attr("width", "100%")
                    .attr("height", height)
                    .attr("viewBox", [-40, -20, width + 100, height + 40])
                    .append("g")
                    .attr("transform", "translate(40, 20)");

                const tree = d3.tree().size([height - 60, width - 260]);
                const root = d3.hierarchy(data);
                tree(root);

                // Links
                svg.selectAll(".link")
                    .data(root.links())
                    .enter()
                    .append("path")
                    .attr("class", "link")
                    .attr("d", d3.linkHorizontal()
                        .x(d => d.y)
                        .y(d => d.x));

                // Nodes
                const node = svg.selectAll(".node")
                    .data(root.descendants())
                    .enter()
                    .append("g")
                    .attr("class", "node")
                    .attr("transform", d => `translate(${{d.y}},${{d.x}})`);

                node.append("circle")
                    .attr("r", d => d.children ? 6 : 4)
                    .style("fill", d => d.depth === 0 ? "#ff007f" : (d.depth === 1 ? "#00f5d4" : "#00bbf9"));

                node.append("text")
                    .attr("dy", "0.31em")
                    .attr("x", d => d.children ? -10 : 10)
                    .attr("text-anchor", d => d.children ? "end" : "start")
                    .text(d => d.data.name);
            </script>
        </body>
        </html>
        """
        components.html(d3_mindmap_html, height=500, scrolling=True)

    with tab3:
        st.markdown("#### Export Scientific Dossier")
        report_md = f"""# BioResearch AI: Scientific Research Dossier
**Query Focus:** {query}

## Mechanism of Action (Mermaid Syntax)
```mermaid
{mermaid_code}
```

## Research Mindmap Structure
```json
{json.dumps(mindmap_data, indent=2)}
```
"""
        st.download_button(
            label="📥 Download Markdown Dossier (.md)",
            data=report_md,
            file_name=f"bioresearch_{query.lower().replace(' ', '_')}.md",
            mime="text/markdown"
        )
        st.download_button(
            label="📥 Download JSON Tree (.json)",
            data=json.dumps(mindmap_data, indent=2),
            file_name=f"mindmap_{query.lower().replace(' ', '_')}.json",
            mime="application/json"
        )
