import io
import json
import unittest
import zipfile
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from research_roots.api import Client, APIError, Sources
from research_roots.identifiers import parse_identifier
from research_roots.metadata import normalize, reconcile
from research_roots.pipeline import build, Settings
from research_roots.analysis import filter_graph, citation_path
from research_roots.exports import bundle, export_files


EV = {'source': 'OpenAlex', 'retrieved_at': '2026-01-01T00:00:00+00:00', 'matching_method': 'openalex', 'url': 'https://api.openalex.org/works/W1'}


def record(number, refs=(), year=2020):
    return {'id': f'https://openalex.org/W{number}', 'title': f'Paper {number}', 'publication_year': year,
            'referenced_works': [f'https://openalex.org/W{r}' for r in refs], 'ids': {}, 'cited_by_count': 10}


class FakeSources:
    def __init__(self):
        self.records = {'W1': record(1, [2, 3, 99]), 'W2': record(2, [4], 2010),
                        'W3': record(3, [4], 2011), 'W4': record(4, [5], None), 'W5': record(5, [], 1990)}

    def work(self, identifier):
        key = parse_identifier(identifier)[1]
        if key not in self.records:
            raise APIError('Missing fixture')
        return self.records[key], dict(EV)

    def citations(self, identifier, limit):
        return [record(6, [1], 2024)][:limit], dict(EV), 1


class PipelineTests(unittest.TestCase):
    def test_identifier_inputs(self):
        for text, expected in [('DOI:10.1234/ABC', ('doi', '10.1234/abc')),
                               ('https://doi.org/10.1234/AbC', ('doi', '10.1234/abc')),
                               ('PMID: 35300707', ('pmid', '35300707')),
                               ('https://pubmed.ncbi.nlm.nih.gov/35300707/', ('pmid', '35300707')),
                               ('https://openalex.org/W123', ('openalex', 'W123'))]:
            self.assertEqual(parse_identifier(text), expected)
        for value in ('', 'paper title', 'Wbad', 'https://evil.example'):
            with self.assertRaises(ValueError):
                parse_identifier(value)

    def test_graph_depth_direction_ancestry_and_missing(self):
        graph = build('W1', sources=FakeSources())
        self.assertEqual({n['id'] for n in graph['nodes']}, {'W1', 'W2', 'W3', 'W4', 'W6'})
        edges = {(e['citing'], e['cited']) for e in graph['edges']}
        self.assertIn(('W6', 'W1'), edges)
        self.assertIn(('W2', 'W4'), edges)
        self.assertNotIn(('W4', 'W5'), edges)
        shared = next(n for n in graph['nodes'] if n['id'] == 'W4')
        self.assertTrue(shared['analysis']['shared_ancestor'])
        self.assertEqual(shared['analysis']['reachable_citing_works'], 4)
        self.assertIsNone(shared['year'])
        self.assertEqual(shared['analysis']['reference_depth'], 2)
        self.assertTrue(any(i['kind'] == 'unresolved_reference' for i in graph['issues']))
        self.assertTrue(all(e['provenance'][0]['retrieved_at'] == EV['retrieved_at'] for e in graph['edges']))
        self.assertEqual(citation_path(graph, 'W6', 'W4'), ['W6', 'W1', 'W2', 'W4'])
        self.assertEqual(citation_path(graph, 'W4', 'W6'), [])

    def test_limits_and_depth_zero(self):
        for settings in [Settings(max_nodes=2), Settings(max_edges=1), Settings(references_per_work=1)]:
            graph = build('W1', settings, FakeSources())
            self.assertLessEqual(len(graph['nodes']), settings.max_nodes)
            self.assertLessEqual(len(graph['edges']), settings.max_edges)
            self.assertTrue(graph['issues'])
        graph = build('W1', Settings(depth=0, citing_limit=0), FakeSources())
        self.assertEqual(len(graph['nodes']), 1)
        self.assertEqual(graph['edges'], [])
        with self.assertRaises(ValueError):
            Settings(depth=3)

    def test_cycles_and_duplicate_references(self):
        sources = FakeSources()
        sources.records['W1'] = record(1, [2, 2])
        sources.records['W2'] = record(2, [1])
        graph = build('W1', sources=sources)
        self.assertEqual(len(graph['edges']), 3)
        self.assertEqual(next(n for n in graph['nodes'] if n['id'] == 'W1')['analysis']['reachable_citing_works'], 2)

    def test_conflicting_identifiers_are_not_merged(self):
        raw = record(1)
        raw['ids'] = {'doi': 'https://doi.org/10.1234/a', 'pmid': 'https://pubmed.ncbi.nlm.nih.gov/123/'}
        node = normalize(raw, EV)
        self.assertFalse(reconcile(node, {'doi': '10.1234/a', 'pmid': '999'}, {'source': 'Europe PMC'}))
        self.assertEqual(node['identifiers']['pmid'], '123')
        self.assertNotIn('Europe PMC', node['source_records'])
        self.assertTrue(node['conflicts'])
        self.assertTrue(reconcile(node, {'doi': '10.1234/a', 'pmid': '123', 'title': 'Different', 'citedByCount': 3}, {'source': 'Europe PMC'}))
        self.assertEqual(node['counts']['Europe PMC']['citations'], 3)

    def test_filters_preserve_consistent_exports(self):
        graph = build('W1', sources=FakeSources())
        filtered = filter_graph(graph, 2000, 2021, 'references', 1)
        ids = {n['id'] for n in filtered['nodes']}
        self.assertEqual(ids, {'W1', 'W2', 'W3'})
        self.assertTrue(all(e['citing'] in ids and e['cited'] in ids for e in filtered['edges']))
        self.assertEqual(graph['manifest']['filters'], {})
        files = export_files(filtered)
        self.assertEqual(json.loads(files['lineage.json'])['nodes'], filtered['nodes'])
        with zipfile.ZipFile(io.BytesIO(bundle(filtered, '<html></html>'))) as archive:
            self.assertEqual(len(archive.namelist()), 8)

    @patch('research_roots.api.time.sleep')
    @patch('research_roots.api.urlopen')
    def test_rate_limit_retry_and_cache_timestamp(self, request, sleep):
        request.side_effect = [HTTPError('url', 429, 'rate limit', {'Retry-After': '1'}, None), io.BytesIO(b'{"ok":true}')]
        client = Client()
        first = client.get('https://api.openalex.org/works/W1')
        second = client.get('https://api.openalex.org/works/W1')
        self.assertEqual(first, second)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(1)
        first[0]['ok'] = False
        self.assertTrue(second[0]['ok'])

    @patch('research_roots.api.time.sleep')
    @patch('research_roots.api.urlopen', side_effect=URLError('offline'))
    def test_network_failure_is_bounded(self, request, sleep):
        with self.assertRaises(APIError):
            Client().get('https://api.openalex.org/works/W1')
        self.assertEqual(request.call_count, 3)

    @patch('research_roots.api.urlopen', side_effect=HTTPError('url', 401, 'unauthorized', {}, None))
    def test_authentication_failure_not_retried(self, request):
        with self.assertRaises(APIError):
            Client().get('https://api.openalex.org/works/W1')
        self.assertEqual(request.call_count, 1)

    def test_resolution_and_ambiguous_results(self):
        client = Client()
        with patch.object(client, 'get', return_value=({'results': [record(1)]}, dict(EV))):
            self.assertEqual(Sources(client).work('35300707')[0]['id'], 'https://openalex.org/W1')
        with patch.object(client, 'get', return_value=({'results': [record(1), record(2)]}, dict(EV))):
            with self.assertRaises(APIError):
                Sources(client).work('35300707')


if __name__ == '__main__':
    unittest.main()
