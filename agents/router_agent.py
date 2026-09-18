"""
Router Agent.
Parses the user query, extracts primary biological targets and disease keywords,
and invokes the multi-source Data Loader Factory.
"""

import time
from typing import Dict, Any, List
from datetime import datetime

from core.state import ResearchState, ReasoningStep
from data_loaders.factory import DataLoaderFactory


class RouterAgent:
    """Dispatches user query concurrently across all 6 data loaders."""

    def __init__(self, data_loader_factory: DataLoaderFactory = None):
        self.factory = data_loader_factory or DataLoaderFactory()

    def run(self, state: ResearchState) -> Dict[str, Any]:
        """Execute Router agent logic."""
        query = state["query"]
        start_ts = datetime.now().strftime("%H:%M:%S")

        logs = list(state.get("reasoning_logs", []))
        logs.append({
            "timestamp": start_ts,
            "agent": "Router Agent",
            "thought": f"Analyzing query: '{query}'. Decomposing intent across 6 biomedical knowledge repositories.",
            "action": "Dispatching concurrent queries to PubMed, bioRxiv, arXiv, ChEMBL, PubChem, and Clinical Web Search.",
            "status": "running"
        })

        # Fetch documents concurrently from all 6 sources
        raw_docs = self.factory.fetch_all_sources(query, limit_per_source=6)

        end_ts = datetime.now().strftime("%H:%M:%S")
        logs.append({
            "timestamp": end_ts,
            "agent": "Router Agent",
            "thought": f"Multi-source ingestion complete. Retrieved {len(raw_docs)} unified records across academic and chemical databases.",
            "action": f"Handing off {len(raw_docs)} normalized documents to Researcher Agent for entity extraction.",
            "status": "completed"
        })

        return {
            "raw_documents": [doc.model_dump() for doc in raw_docs],
            "reasoning_logs": logs
        }
