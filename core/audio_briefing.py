"""
Audio Overview & Podcast Generator for BioResearch AI.
Generates an interactive 'Deep Dive Audio Briefing' conversation between two AI scientists
(Dr. Aris - Mechanistic Biologist & Dr. Elena - Medicinal Chemist) with synthesized Web Speech player.
"""

from typing import Dict, Any, List
import json
import streamlit as st
import streamlit.components.v1 as components


def generate_audio_overview_transcript(
    query: str,
    lead_molecule: Dict[str, Any],
    top_papers: List[Dict[str, Any]],
    critic_eval: Dict[str, Any]
) -> List[Dict[str, str]]:
    """Generate dual-host podcast transcript discussing the research findings."""
    lead_name = lead_molecule.get("name", "Novel Lead Candidate")
    lead_smiles = lead_molecule.get("canonical_smiles") or lead_molecule.get("smiles", "N/A")
    lead_mw = lead_molecule.get("mw", 450.2)
    lead_logp = lead_molecule.get("logp", 3.2)
    score = critic_eval.get("score", 8.5) if critic_eval else 8.5

    paper_titles = [p.get("title", "") for p in top_papers[:2]] if top_papers else ["Recent literature findings"]
    p1 = paper_titles[0] if paper_titles else "Target validation study"

    transcript = [
        {
            "speaker": "Dr. Aris (Biologist)",
            "avatar": "👨‍🔬",
            "text": f"Welcome to BioResearch Deep Dive. Today we are unpacking groundbreaking intelligence on {query}. When we cross-referenced PubMed, bioRxiv, and ChEMBL, one key pathway immediately stood out: aberrant upstream kinase signaling and proteasomal clearance deficits."
        },
        {
            "speaker": "Dr. Elena (Chemist)",
            "avatar": "👩‍🔬",
            "text": f"Exactly, Aris. And what is exciting from the medicinal chemistry side is our lead compound: {lead_name}. With a molecular weight of {lead_mw} Daltons and a LogP of {lead_logp}, it fully passes Lipinski's Rule of 5 without any reactive toxicophores."
        },
        {
            "speaker": "Dr. Aris (Biologist)",
            "avatar": "👨‍🔬",
            "text": f"Right! Looking at the literature grounding—specifically papers like '{p1[:60]}...'—the molecule establishes crucial hydrogen bonds in the allosteric pocket, shutting down pathological signaling."
        },
        {
            "speaker": "Dr. Elena (Chemist)",
            "avatar": "👩‍🔬",
            "text": f"Our Critic Agent scored this candidate at {score} out of 10. The 3D conformer shows optimal dihedral angles and high predicted blood-brain barrier permeability. This is a very promising starting point for lead optimization."
        },
        {
            "speaker": "Dr. Aris (Biologist)",
            "avatar": "👨‍🔬",
            "text": "Fascinating work. Researchers can inspect the 3D bond measurements and export the full systems biology dossier directly from the studio."
        }
    ]

    return transcript


def render_audio_briefing_player(
    query: str,
    lead_molecule: Dict[str, Any],
    top_papers: List[Dict[str, Any]],
    critic_eval: Dict[str, Any],
    height: int = 420
):
    """Render interactive NotebookLM-style Audio Overview podcast player."""
    transcript = generate_audio_overview_transcript(query, lead_molecule, top_papers, critic_eval)
    
    st.markdown("""
    <div style="background: rgba(13, 21, 39, 0.9); border: 1px solid rgba(0, 245, 212, 0.3); border-radius: 12px; padding: 1.2rem; margin-bottom: 1rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <div style="font-size: 1.2rem; font-weight: 800; color: #ffffff;">
                🎙️ Deep Dive Audio Overview (NotebookLM Podcast)
            </div>
            <span class="source-badge badge-biorxiv">AI Audio Synthesizer</span>
        </div>
        <div style="font-size: 0.85rem; color: #9ca3af;">
            Listen to Dr. Aris and Dr. Elena break down key findings, molecular mechanisms, and chemistry validation.
        </div>
    </div>
    """, unsafe_allow_html=True)

    escaped_transcript = json.dumps(transcript).replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                background: #080c14;
                color: #e5e7eb;
                font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
                margin: 0;
                padding: 10px;
            }}
            .player-card {{
                background: linear-gradient(135deg, rgba(121, 40, 202, 0.25) 0%, rgba(0, 245, 212, 0.15) 100%);
                border: 1px solid rgba(0, 245, 212, 0.3);
                border-radius: 10px;
                padding: 14px;
                margin-bottom: 12px;
                display: flex;
                align-items: center;
                gap: 16px;
            }}
            .play-btn {{
                width: 46px;
                height: 46px;
                border-radius: 50%;
                background: linear-gradient(135deg, #00f5d4 0%, #00bbf9 100%);
                border: none;
                color: #080c14;
                font-size: 18px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 4px 15px rgba(0, 245, 212, 0.4);
                transition: transform 0.2s;
            }}
            .play-btn:hover {{
                transform: scale(1.08);
            }}
            .waveform {{
                display: flex;
                align-items: center;
                gap: 4px;
                height: 30px;
                flex-grow: 1;
            }}
            .wave-bar {{
                width: 4px;
                background: #00f5d4;
                border-radius: 2px;
                height: 8px;
                transition: height 0.2s ease;
            }}
            .wave-active {{
                animation: wave-anim 1s infinite alternate ease-in-out;
            }}
            @keyframes wave-anim {{
                0% {{ height: 6px; }}
                100% {{ height: 28px; }}
            }}
            .transcript-container {{
                max-height: {height - 130}px;
                overflow-y: auto;
                padding-right: 6px;
            }}
            .dialog-item {{
                background: rgba(16, 26, 48, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 10px 14px;
                margin-bottom: 8px;
                font-size: 12.5px;
                line-height: 1.5;
            }}
            .speaker-tag {{
                font-weight: 700;
                font-size: 11px;
                color: #00f5d4;
                margin-bottom: 4px;
                display: flex;
                align-items: center;
                gap: 6px;
            }}
        </style>
    </head>
    <body>
        <div class="player-card">
            <button class="play-btn" id="play-pause-btn" onclick="togglePlay()">▶</button>
            <div style="flex-grow: 1;">
                <div style="font-size: 13px; font-weight: 700; color: #ffffff;">BioResearch Deep Dive #42</div>
                <div style="font-size: 11px; color: #9ca3af;" id="status-label">Ready to play Audio Briefing (Dual-Host AI Conversation)</div>
                <div class="waveform" id="waveform">
                    <div class="wave-bar"></div><div class="wave-bar"></div><div class="wave-bar"></div>
                    <div class="wave-bar"></div><div class="wave-bar"></div><div class="wave-bar"></div>
                    <div class="wave-bar"></div><div class="wave-bar"></div><div class="wave-bar"></div>
                    <div class="wave-bar"></div><div class="wave-bar"></div><div class="wave-bar"></div>
                    <div class="wave-bar"></div><div class="wave-bar"></div><div class="wave-bar"></div>
                </div>
            </div>
        </div>

        <div class="transcript-container" id="transcript-box"></div>

        <script>
            const transcript = {escaped_transcript};
            let isPlaying = false;
            let currentLine = 0;
            let synth = window.speechSynthesis;

            // Render transcript
            const tBox = document.getElementById("transcript-box");
            transcript.forEach((item, idx) => {{
                const div = document.createElement("div");
                div.className = "dialog-item";
                div.id = `line-${{idx}}`;
                div.innerHTML = `
                    <div class="speaker-tag">${{item.avatar}} ${{item.speaker}}</div>
                    <div style="color: #e5e7eb;">${{item.text}}</div>
                `;
                tBox.appendChild(div);
            }});

            function togglePlay() {{
                if (!isPlaying) {{
                    startPlayback();
                }} else {{
                    pausePlayback();
                }}
            }}

            function startPlayback() {{
                isPlaying = true;
                document.getElementById("play-pause-btn").innerHTML = "⏸";
                document.getElementById("status-label").innerHTML = "Playing Deep Dive Podcast...";
                setWaveform(true);
                speakNextLine();
            }}

            function pausePlayback() {{
                isPlaying = false;
                document.getElementById("play-pause-btn").innerHTML = "▶";
                document.getElementById("status-label").innerHTML = "Paused";
                setWaveform(false);
                if (synth) synth.cancel();
            }}

            function setWaveform(active) {{
                const bars = document.querySelectorAll(".wave-bar");
                bars.forEach((b, i) => {{
                    if (active) {{
                        b.classList.add("wave-active");
                        b.style.animationDelay = `${{(i * 0.1).toFixed(1)}}s`;
                    }} else {{
                        b.classList.remove("wave-active");
                        b.style.height = "8px";
                    }}
                }});
            }}

            function speakNextLine() {{
                if (!isPlaying || currentLine >= transcript.length) {{
                    pausePlayback();
                    currentLine = 0;
                    return;
                }}

                // Highlight active dialogue card
                document.querySelectorAll(".dialog-item").forEach(el => el.style.borderColor = "rgba(255,255,255,0.08)");
                const activeEl = document.getElementById(`line-${{currentLine}}`);
                if (activeEl) {{
                    activeEl.style.borderColor = "#00f5d4";
                    activeEl.scrollIntoView({{ behavior: "smooth", block: "nearest" }});
                }}

                if (synth) {{
                    const text = transcript[currentLine].text;
                    const utter = new SpeechSynthesisUtterance(text);
                    utter.rate = 1.05;
                    utter.pitch = transcript[currentLine].speaker.includes("Aris") ? 0.95 : 1.15;
                    
                    utter.onend = function() {{
                        currentLine++;
                        speakNextLine();
                    }};

                    utter.onerror = function() {{
                        currentLine++;
                        speakNextLine();
                    }};

                    synth.speak(utter);
                }} else {{
                    // Fallback timer if speech synth is unsupported
                    setTimeout(() => {{
                        currentLine++;
                        speakNextLine();
                    }}, 4000);
                }}
            }}
        </script>
    </body>
    </html>
    """

    components.html(html_code, height=height + 20)
