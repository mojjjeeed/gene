"""
Unit Tests for LangGraph Multi-Agent Workflow Engine with Domain Queries.
"""

import unittest
from core.workflow import BioResearchWorkflow


class TestWorkflow(unittest.TestCase):

    def setUp(self):
        self.workflow = BioResearchWorkflow()

    def test_anger_management_query(self):
        query = "anger management"
        result_state = self.workflow.run(query)

        self.assertIsNotNone(result_state)
        self.assertEqual(result_state["query"], query)
        
        # Verify papers retrieved
        ranked_docs = result_state["ranked_documents"]
        self.assertGreaterEqual(len(ranked_docs), 1)

        # Verify chemical analysis is tailored
        chem = result_state["chemical_analysis"]
        self.assertGreaterEqual(len(chem), 1)
        lead_mol = chem[0]
        self.assertIn("canonical_smiles", lead_mol)
        
        # Verify mechanism is relevant to CNS/neuro/serotonin/adrenergic
        mech_text = f"{lead_mol.get('mechanism', '')} {lead_mol.get('rationale', '')}".lower()
        self.assertTrue(any(w in mech_text for w in ["5-ht", "serotonin", "adrenergic", "amygdala", "cns", "propranolol", "buspirone", "anger", "receptor", "neurological"]))


if __name__ == "__main__":
    unittest.main()
