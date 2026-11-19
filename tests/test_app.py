import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch
from test_pipeline import FakeSources
from research_roots.pipeline import build


@unittest.skipUnless(importlib.util.find_spec('streamlit') and importlib.util.find_spec('plotly'), 'UI dependencies not installed')
class AppTests(unittest.TestCase):
    def test_lookup_filter_and_export_render(self):
        from streamlit.testing.v1 import AppTest
        graph = build('W1', sources=FakeSources())
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        with patch('research_roots.pipeline.build', return_value=graph):
            app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.tabs), 5)
        app.selectbox[0].select('references').run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.get('download_button'))
