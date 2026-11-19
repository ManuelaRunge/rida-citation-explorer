import unittest
from unittest.mock import Mock
from research_roots.api import Sources, APIError
from research_roots.citations import biomedical_node, merge_node, citing_rows
from research_roots.analysis import author_group, author_key
from research_roots.pipeline import build, Settings
from test_pipeline import FakeSources, record, EV


class CitationTests(unittest.TestCase):
    def test_openalex_pagination_and_page_provenance(self):
        client = Mock()
        client.get.side_effect = [({'results': [record(i) for i in range(100)], 'meta': {'count': 102}}, dict(EV)),
                                  ({'results': [record(100), record(101)], 'meta': {'count': 102}}, {**EV, 'url': 'page2'})]
        records, report, total = Sources(client).citations('W1', 150)
        self.assertEqual(len(records), 102)
        self.assertEqual(client.get.call_args_list[1].args[1]['page'], 2)
        self.assertEqual(records[-1]['_evidence']['url'], 'page2')
        self.assertEqual(len(report['pages']), 2)

    def test_partial_pagination_retains_successful_records(self):
        client = Mock()
        client.get.side_effect = [({'results': [record(i) for i in range(100)], 'meta': {'count': 200}}, dict(EV)), APIError('offline')]
        records, report, total = Sources(client).citations('W1', 200)
        self.assertEqual(len(records), 100)
        self.assertIn('error', report)

    def test_europe_paging(self):
        client = Mock()
        client.get.return_value = ({'hitCount': 1, 'citationList': {'citation': [{'id': '42', 'source': 'MED'}]}}, dict(EV))
        records, report, total = Sources(client).europe_citations('123', 100)
        self.assertEqual(total, 1)
        self.assertEqual(records[0]['_evidence']['source'], 'Europe PMC')
        self.assertEqual(client.get.call_args.args[1]['pageSize'], 100)

    def test_pubmed_only_citedin_links_and_summary_provenance(self):
        client = Mock()
        client.get.side_effect = [({'linksets': [{'linksetdbs': [
            {'linkname': 'pubmed_pubmed', 'links': ['999']},
            {'linkname': 'pubmed_pubmed_citedin', 'links': ['20', '21']}]}]}, dict(EV)),
            ({'result': {'21': {'uid': '21', 'title': 'A', 'pubdate': '2025 Jan', 'authors': [{'name': 'Smith J'}]}}}, {**EV, 'url': 'summary'})]
        records, report, total = Sources(client).pubmed_citations('123', 1)
        self.assertEqual(total, 2)
        self.assertEqual(len(records), 1)
        node = biomedical_node(records[0], 'PubMed')
        self.assertEqual(node['identifiers']['pmid'], '21')
        self.assertEqual(node['provenance'][0]['url'], 'summary')
        self.assertEqual(node['year'], 2025)

    def test_union_and_source_evidence_and_citer_priority(self):
        sources = FakeSources()
        sources.records['W1']['ids'] = {'pmid': '123'}
        sources.europe = lambda *args: (None, {})
        oa = record(6, year=2024)
        oa['ids'] = {'pmid': '42'}
        sources.citations = lambda *args: ([oa], dict(EV), 1)
        epmc = {'source': 'MED', 'id': '42', 'title': 'Citing study', 'pubYear': 2024, 'authorString': 'Smith J'}
        sources.europe_citations = lambda *args: ([{**epmc, '_evidence': {**EV, 'source': 'Europe PMC'}}], {}, 1)
        sources.pubmed_citations = lambda *args: ([{'uid': '42', 'title': 'Citing study', 'pubdate': '2024',
            '_evidence': {**EV, 'source': 'PubMed'}}], {}, 1)
        graph = build('W1', Settings(max_nodes=2), sources)
        self.assertEqual(len(graph['nodes']), 2)
        edge = graph['edges'][0]
        self.assertEqual((edge['citing'], edge['cited']), ('W6', 'W1'))
        self.assertEqual({p['source'] for p in edge['provenance']}, {'OpenAlex', 'Europe PMC', 'PubMed'})
        self.assertEqual(len(citing_rows(graph)), 1)

    def test_conflicting_dois_not_merged(self):
        a = biomedical_node({'uid': '1', 'title': 'One', 'articleids': [{'idtype': 'doi', 'value': '10.1234/a'}], '_evidence': EV}, 'PubMed')
        b = biomedical_node({'id': '1', 'source': 'MED', 'doi': '10.1234/b', '_evidence': EV}, 'Europe PMC')
        nodes, issues = {}, []
        merge_node(nodes, a, issues)
        merge_node(nodes, b, issues)
        self.assertEqual(len(nodes), 2)
        self.assertEqual(issues[0]['kind'], 'identifier_conflict')

    def test_author_hints_and_missing_authors(self):
        seed = {'id': '1', 'authors': ['Manuela Runge', 'Emilie Pothin']}
        self.assertEqual(author_group(seed, {'id': '2', 'authors': ['Smith J', 'Pothin E']}), 'Seed last author')
        self.assertEqual(author_group(seed, {'id': '2', 'authors': ['Runge M', 'Pothin E']}), 'Both seed authors')
        self.assertEqual(author_group(seed, {'id': '2', 'authors': []}), 'Unknown authors')
        self.assertEqual(author_group(seed, {'id': '2', 'authors': ['Runge X']}), 'No match')
        self.assertIsNone(author_key('Consortium'))
