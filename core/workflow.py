"""
LangGraph Multi-Agent Workflow Engine.
Orchestrates the 5 specialized AI agents (Router, Researcher, Re-ranker, Chemist, Critic, Synthesizer)
with an automated DPO (Direct Preference Optimization) Self-Correction Loop.
"""

import time
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END

from core.state import ResearchState
from agents.router_agent import RouterAgent
from agents.researcher_agent import ResearcherAgent
from agents.reranker_agent import ReRankerAgent
from agents.chemist_agent import ChemistAgent
from agents.critic_agent import CriticAgent
from agents.synthesizer_agent import SynthesizerAgent
import config


class BioResearchWorkflow:
    """Builds and executes the LangGraph multi-agent DAG with self-correction."""

    def __init__(self):
        self.router_agent = RouterAgent()
        self.researcher_agent = ResearcherAgent()
        self.reranker_agent = ReRankerAgent()
        self.chemist_agent = ChemistAgent()
        self.critic_agent = CriticAgent()
        self.synthesizer_agent = SynthesizerAgent()
        self.graph = self._build_graph()

    def _build_graph(self):
        """Construct the LangGraph StateGraph."""
        builder = StateGraph(ResearchState)

        # 1. Add Agent Nodes
        builder.add_node("router", self.router_agent.run)
        builder.add_node("researcher", self.researcher_agent.run)
        builder.add_node("reranker", self.reranker_agent.run)
        builder.add_node("chemist", self.chemist_agent.run)
        builder.add_node("critic", self.critic_agent.run)
        builder.add_node("synthesizer", self.synthesizer_agent.run)

        # 2. Define Primary Execution Edges
        builder.add_edge(START, "router")
        builder.add_edge("router", "researcher")
        builder.add_edge("researcher", "reranker")
        builder.add_edge("reranker", "chemist")
        builder.add_edge("chemist", "critic")

        # 3. Conditional Edge for DPO Validation Loop
        def should_loop_back(state: ResearchState) -> Literal["researcher", "synthesizer"]:
            critic_eval = state.get("critic_evaluation", {})
            score = critic_eval.get("score", 10.0)
            passed = critic_eval.get("passed", True)
            revision_count = state.get("revision_count", 0)
            max_revisions = state.get("max_revisions", config.MAX_REVISION_LOOPS)

            if not passed and revision_count < max_revisions:
                print(f"[Workflow] Critic score {score} < {config.CRITIC_PASSING_SCORE}. DPO Loop #{revision_count} triggered!")
                return "researcher"
            return "synthesizer"

        builder.add_conditional_edges(
            "critic",
            should_loop_back,
            {
                "researcher": "researcher",
                "synthesizer": "synthesizer"
            }
        )

        builder.add_edge("synthesizer", END)
        return builder.compile()

    def run(self, query: str, focus_target: str = None) -> ResearchState:
        """Run the full autonomous multi-agent pipeline for a query."""
        initial_state: ResearchState = {
            "query": query,
            "focus_target": focus_target,
            "raw_documents": [],
            "ranked_documents": [],
            "extracted_entities": {},
            "chemical_analysis": [],
            "critic_evaluation": None,
            "revision_count": 0,
            "max_revisions": config.MAX_REVISION_LOOPS,
            "reasoning_logs": [],
            "final_synthesis": None,
            "notebook_data": None,
            "execution_time_seconds": 0.0
        }

        start_time = time.time()
        final_state = self.graph.invoke(initial_state)
        elapsed = round(time.time() - start_time, 2)
        final_state["execution_time_seconds"] = elapsed
        print(f"[Workflow] Multi-agent execution completed in {elapsed} seconds.")
        return final_state
