"""
Unit Tests for Photorealistic 3D Bond Inspector & Physiological Annotations.
"""

import unittest
from ui.bond_inspector import extract_photorealistic_graph_details, compute_functional_group_body_effect


class TestBondInspector(unittest.TestCase):

    def test_extract_photorealistic_graph_details(self):
        # Propranolol (Anger / Beta-adrenergic & 5-HT1A)
        smiles = "CC(C)NCC(O)COC1=CC=CC2=CC=CC=C12"
        details = extract_photorealistic_graph_details(smiles)

        self.assertIsNotNone(details)
        self.assertIn("molblock_3d", details)
        self.assertIn("atoms", details)
        self.assertIn("bonds", details)

        atoms = details["atoms"]
        self.assertGreater(len(atoms), 10)
        self.assertIn("biological_role", atoms[0])

        bonds = details["bonds"]
        self.assertGreater(len(bonds), 10)
        self.assertIn("body_effect", bonds[0])
        self.assertIn("significance", bonds[0])

    def test_compute_functional_group_body_effect(self):
        # Amide/Amine C-N
        effect_cn = compute_functional_group_body_effect("C1", "N2", "SINGLE", 1.45)
        self.assertIn("body_effect", effect_cn)
        self.assertIn("blood-brain barrier", effect_cn["body_effect"].lower())

        # Carbonyl C=O
        effect_co = compute_functional_group_body_effect("C1", "O2", "DOUBLE", 1.23)
        self.assertIn("hydrogen bond acceptor", effect_co["body_effect"].lower())


if __name__ == "__main__":
    unittest.main()
