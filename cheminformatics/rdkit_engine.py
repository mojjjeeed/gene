"""
RDKit Cheminformatics Engine for BioResearch AI.
Provides molecular property calculation, Lipinski Rule of 5 validation,
Veber rule checks, toxicophore / PAINS structural alert filtering,
and 3D conformer generation for py3Dmol visualization.
"""

from typing import Dict, Any, List, Optional, Tuple
import re

from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski, AllChem, Draw, rdMolDescriptors
from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams

import config


# Predefined SMARTS patterns for common toxicophores and reactive functional groups
TOXICOPHORE_SMARTS = {
    "Aldehyde": "[CX3H1](=O)[#6,#1]",
    "Aliphatic Halide (Alkyl Halide)": "[CX4][Cl,Br,I]",
    "Acyl Halide": "[CX3](=[OX1])[Cl,Br,I]",
    "Alkyl Nitrate": "[CX4]O[NX3+](=O)[O-]",
    "Azide": "[NX1]~[NX2]~[NX1]",
    "Epoxide / Oxirane": "[OX2]1[CX4][CX4]1",
    "Michael Acceptor (alpha,beta-unsaturated carbonyl)": "[CX3]=[CX3][CX3](=[OX1])",
    "Nitro Group (Aliphatic/Reactive)": "[$([NX3+](=O)[O-]),$([NX3]=O)]",
    "Isocyanate": "[NX2]=[CX2]=[OX1]",
    "Isothiocyanate": "[NX2]=[CX2]=[SX1]",
    "Thioester": "[CX3](=[OX1])[SX2]",
    "Hydrazine": "[NX3][NX3]",
    "Phosphonium / Phosphine": "[PX4,PX3]",
    "Thiourea": "[NX3][CX3](=[SX1])[NX3]"
}

# Initialize compiled SMARTS patterns
COMPILED_TOXICOPHORES = {
    name: Chem.MolFromSmarts(smarts)
    for name, smarts in TOXICOPHORE_SMARTS.items()
    if Chem.MolFromSmarts(smarts) is not None
}

# Try initializing RDKit built-in PAINS catalog if available
try:
    pains_params = FilterCatalogParams()
    pains_params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
    PAINS_CATALOG = FilterCatalog(pains_params)
except Exception:
    PAINS_CATALOG = None


class RDKitEngine:
    """Cheminformatics processor for molecular validation and 3D modeling."""

    @staticmethod
    def parse_smiles(smiles: str) -> Optional[Chem.Mol]:
        """Validate and sanitize a SMILES string."""
        if not smiles or not isinstance(smiles, str):
            return None
        
        # Clean common markdown or punctuation artifacts
        cleaned = smiles.strip().strip("`'\".,;()[]{}")
        try:
            mol = Chem.MolFromSmiles(cleaned)
            if mol is not None:
                Chem.SanitizeMol(mol)
                return mol
        except Exception:
            pass
        return None

    @staticmethod
    def calculate_properties(mol: Chem.Mol) -> Dict[str, Any]:
        """Compute Lipinski and Veber molecular descriptors."""
        mw = round(Descriptors.MolWt(mol), 2)
        logp = round(Descriptors.MolLogP(mol), 2)
        hbd = int(Lipinski.NumHDonors(mol))
        hba = int(Lipinski.NumHAcceptors(mol))
        rot_bonds = int(Lipinski.NumRotatableBonds(mol))
        tpsa = round(Descriptors.TPSA(mol), 2)
        heavy_atom_count = int(mol.GetNumHeavyAtoms())
        
        # Formula
        formula = rdMolDescriptors.CalcMolFormula(mol)
        canonical_smiles = Chem.MolToSmiles(mol, canonical=True)

        # Lipinski Rule of 5 Evaluation
        mw_pass = mw <= config.LIPINSKI_RULES["max_mw"]
        logp_pass = logp <= config.LIPINSKI_RULES["max_logp"]
        hbd_pass = hbd <= config.LIPINSKI_RULES["max_hbd"]
        hba_pass = hba <= config.LIPINSKI_RULES["max_hba"]
        
        # Veber Rules
        rot_pass = rot_bonds <= config.LIPINSKI_RULES["max_rotatable_bonds"]
        tpsa_pass = tpsa <= config.LIPINSKI_RULES["max_tpsa"]

        rule_of_5_violations = sum([not mw_pass, not logp_pass, not hbd_pass, not hba_pass])
        passes_lipinski = rule_of_5_violations <= 1  # 1 violation permitted by strict Lipinski criteria
        passes_veber = rot_pass and tpsa_pass

        return {
            "canonical_smiles": canonical_smiles,
            "molecular_formula": formula,
            "mw": mw,
            "logp": logp,
            "hbd": hbd,
            "hba": hba,
            "rotatable_bonds": rot_bonds,
            "tpsa": tpsa,
            "heavy_atom_count": heavy_atom_count,
            "passes_lipinski": passes_lipinski,
            "passes_veber": passes_veber,
            "rule_of_5_violations": rule_of_5_violations,
            "mw_pass": mw_pass,
            "logp_pass": logp_pass,
            "hbd_pass": hbd_pass,
            "hba_pass": hba_pass
        }

    @classmethod
    def detect_toxicophores_and_pains(cls, mol: Chem.Mol) -> Tuple[List[str], bool]:
        """Detect toxicophores and PAINS (Pan Assay Interference Compounds) substructures."""
        alerts: List[str] = []

        # 1. Custom SMARTS toxicophores
        for name, query_mol in COMPILED_TOXICOPHORES.items():
            if query_mol and mol.HasSubstructMatch(query_mol):
                alerts.append(f"Toxicophore: {name}")

        # 2. RDKit PAINS catalog
        if PAINS_CATALOG:
            try:
                matches = PAINS_CATALOG.GetMatches(mol)
                for match in matches:
                    alerts.append(f"PAINS Alert: {match.GetDescription()}")
            except Exception:
                pass

        has_toxicophore = len(alerts) > 0
        return alerts, has_toxicophore

    @classmethod
    def generate_3d_conformer(cls, mol: Chem.Mol, max_attempts: int = 50) -> Optional[str]:
        """Generate energy-minimized 3D coordinates using ETKDG and MMFF94 force field."""
        try:
            # Create a copy with Hydrogens added for proper 3D geometry
            mol_3d = Chem.AddHs(mol)
            
            # Embed with ETKDG (Experimental-Torsion Knowledge Distance Geometry)
            params = AllChem.ETKDGv3() if hasattr(AllChem, 'ETKDGv3') else AllChem.ETKDG()
            params.randomSeed = 42
            params.maxIterations = max_attempts
            
            embed_res = AllChem.EmbedMolecule(mol_3d, params)
            if embed_res != 0:
                # Fallback to standard embedding
                AllChem.EmbedMolecule(mol_3d, randomSeed=42)
            
            # Optimize conformer using MMFF94 force field
            try:
                AllChem.MMFFOptimizeMolecule(mol_3d, maxIters=200)
            except Exception:
                # Fallback to UFF if MMFF fails
                try:
                    AllChem.UFFOptimizeMolecule(mol_3d, maxIters=200)
                except Exception:
                    pass

            # Export to MolBlock format (readable by py3Dmol)
            molblock = Chem.MolToMolBlock(mol_3d)
            return molblock
        except Exception:
            # Fallback: export 2D molblock if 3D embedding fails
            try:
                AllChem.Compute2DCoords(mol)
                return Chem.MolToMolBlock(mol)
            except Exception:
                return None

    @classmethod
    def generate_2d_svg(cls, mol: Chem.Mol, width: int = 350, height: int = 250) -> str:
        """Generate high-resolution 2D SVG representation with modern dark styling."""
        try:
            drawer = Draw.rdMolDraw2D.MolDraw2DSVG(width, height)
            opts = drawer.drawOptions()
            opts.clearBackground = True
            opts.bondLineWidth = 2
            opts.padding = 0.1
            
            # Draw molecule
            drawer.DrawMolecule(mol)
            drawer.FinishDrawing()
            svg = drawer.GetDrawingText()
            return svg
        except Exception:
            return ""

    @classmethod
    def analyze_molecule(cls, smiles: str, name: str = "Unknown Candidate") -> Optional[Dict[str, Any]]:
        """Full automated pipeline: validation -> properties -> PAINS -> 3D conformer."""
        mol = cls.parse_smiles(smiles)
        if mol is None:
            return None

        props = cls.calculate_properties(mol)
        alerts, has_toxicophore = cls.detect_toxicophores_and_pains(mol)
        molblock_3d = cls.generate_3d_conformer(mol)
        svg_2d = cls.generate_2d_svg(mol)

        return {
            "name": name,
            "smiles": smiles,
            "canonical_smiles": props["canonical_smiles"],
            "molecular_formula": props["molecular_formula"],
            "mw": props["mw"],
            "logp": props["logp"],
            "hbd": props["hbd"],
            "hba": props["hba"],
            "rotatable_bonds": props["rotatable_bonds"],
            "tpsa": props["tpsa"],
            "heavy_atom_count": props["heavy_atom_count"],
            "passes_lipinski": props["passes_lipinski"],
            "passes_veber": props["passes_veber"],
            "rule_of_5_violations": props["rule_of_5_violations"],
            "pains_alerts": alerts,
            "has_toxicophore": has_toxicophore,
            "conformer_3d_molblock": molblock_3d,
            "svg_2d": svg_2d
        }
