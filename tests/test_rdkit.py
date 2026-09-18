"""
Unit Tests for RDKit Cheminformatics Engine.
"""

import unittest
from cheminformatics.rdkit_engine import RDKitEngine


class TestRDKitEngine(unittest.TestCase):

    def setUp(self):
        self.engine = RDKitEngine()
        # Aspirin
        self.aspirin_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
        # Imatinib
        self.imatinib_smiles = "CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5"
        # Invalid SMILES
        self.invalid_smiles = "INVALID_SMILES_12345"

    def test_parse_smiles(self):
        mol_valid = self.engine.parse_smiles(self.aspirin_smiles)
        self.assertIsNotNone(mol_valid)

        mol_invalid = self.engine.parse_smiles(self.invalid_smiles)
        self.assertIsNone(mol_invalid)

    def test_calculate_properties(self):
        mol = self.engine.parse_smiles(self.aspirin_smiles)
        props = self.engine.calculate_properties(mol)
        
        self.assertAlmostEqual(props["mw"], 180.16, delta=1.0)
        self.assertLess(props["logp"], 5.0)
        self.assertTrue(props["passes_lipinski"])
        self.assertEqual(props["hbd"], 1)
        self.assertEqual(props["hba"], 3)

    def test_toxicophore_detection(self):
        # Aldehyde containing toxicophore: Benzaldehyde
        aldehyde_smiles = "c1ccccc1C=O"
        mol_ald = self.engine.parse_smiles(aldehyde_smiles)
        alerts, has_toxicophore = self.engine.detect_toxicophores_and_pains(mol_ald)
        self.assertTrue(has_toxicophore)
        self.assertTrue(any("Aldehyde" in a for a in alerts))

        # Aspirin should not trigger severe toxicophore
        mol_asp = self.engine.parse_smiles(self.aspirin_smiles)
        alerts_asp, _ = self.engine.detect_toxicophores_and_pains(mol_asp)
        self.assertFalse(any("Aldehyde" in a for a in alerts_asp))

    def test_generate_3d_conformer(self):
        mol = self.engine.parse_smiles(self.aspirin_smiles)
        molblock = self.engine.generate_3d_conformer(mol)
        self.assertIsNotNone(molblock)
        self.assertIn("M  END", molblock)

    def test_full_molecule_analysis(self):
        analysis = self.engine.analyze_molecule(self.imatinib_smiles, name="Imatinib")
        self.assertIsNotNone(analysis)
        self.assertEqual(analysis["name"], "Imatinib")
        self.assertTrue(analysis["passes_lipinski"])
        self.assertIn("conformer_3d_molblock", analysis)


if __name__ == "__main__":
    unittest.main()
