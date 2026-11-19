"""Explicitly opt-in API smoke test; never asserts a fixed citation network."""
import os
import unittest
from research_roots.pipeline import build, Settings


@unittest.skipUnless(os.environ.get('RESEARCH_ROOTS_LIVE') == '1', 'Live APIs are opt-in')
class LiveTests(unittest.TestCase):
    def test_example_pmid(self):
        result = build('35300707', Settings(depth=1, max_nodes=5, references_per_work=2, citing_limit=1))
        self.assertTrue(result['nodes'][0]['title'])
        self.assertEqual(result['manifest']['seed_identifiers'].get('pmid'), '35300707')
