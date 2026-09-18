"""
Unit Tests for Multi-Source Data Loaders.
"""

import unittest
from data_loaders.pubmed_loader import PubMedLoader
from data_loaders.pubchem_loader import PubChemLoader
from data_loaders.factory import DataLoaderFactory


class TestDataLoaders(unittest.TestCase):

    def test_pubchem_loader_resolve(self):
        loader = PubChemLoader()
        info = loader.resolve_compound("Donepezil")
        self.assertIsNotNone(info)
        self.assertIn("CanonicalSMILES", info)

    def test_pubmed_loader_search(self):
        loader = PubMedLoader()
        # Search common query
        docs = loader.search("Alzheimer BACE1", limit=3)
        self.assertIsInstance(docs, list)

    def test_factory_concurrent_fetch(self):
        factory = DataLoaderFactory()
        docs = factory.fetch_all_sources("Alzheimer disease", limit_per_source=2)
        self.assertIsInstance(docs, list)
        self.assertGreater(len(docs), 0)


if __name__ == "__main__":
    unittest.main()
