"""
Configuration module for BioResearch AI.
Handles API keys, model parameters, cheminformatics thresholds, and runtime settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# LLM Configurations
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

# Default LLM Provider: 'gemini', 'openai', 'anthropic', 'ollama', or 'heuristic'
DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "auto")
DEFAULT_MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME", "gemini-2.0-flash")

# NCBI / PubMed API Settings
NCBI_EMAIL = os.getenv("NCBI_EMAIL", "bioresearch_ai@deeptech.org")
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")

# Cheminformatics Thresholds (Lipinski's Rule of 5 + Veber Rules)
LIPINSKI_RULES = {
    "max_mw": 500.0,          # Molecular Weight < 500 Da
    "max_logp": 5.0,          # LogP < 5.0
    "max_hbd": 5,             # H-Bond Donors < 5
    "max_hba": 10,            # H-Bond Acceptors < 10
    "max_rotatable_bonds": 10,# Rotatable Bonds <= 10
    "max_tpsa": 140.0         # TPSA <= 140.0 Å²
}

# DPO & Multi-Agent Parameters
CRITIC_PASSING_SCORE = 7.0   # Score threshold to pass DPO check (scale 1-10)
MAX_REVISION_LOOPS = 2       # Max self-correction loops

# Cache & Storage
DATA_CACHE_DIR = BASE_DIR / "cache"
DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
