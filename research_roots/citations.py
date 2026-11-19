"""Forward citation discovery with conservative cross-source identity matching."""
import html
import re
from urllib.parse import quote

from .api import APIError
from .metadata import normalize


def clean(text):
    return re.sub('<[^>]+>', '', html.unescape(text or '')).strip()


def biomedical_node(raw, source):
    ids = {}
    if source == 'PubMed':
        ids['pmid'] = str(raw['uid'])
        for item in raw.get('articleids', []):
            if item.get('idtype') in ('doi', 'pmc'):
                ids['pmcid' if item['idtype'] == 'pmc' else 'doi'] = item['value']
        authors = [a['name'] for a in raw.get('authors', []) if a.get('name')]
        date = raw.get('pubdate')
        match = re.match(r'\d{4}', date or '')
        year = int(match[0]) if match else None
        journal, kind = raw.get('fulljournalname'), '; '.join(raw.get('pubtype', [])) or None
        identifier = 'PMID:' + ids['pmid']
    else:
        source_id = str(raw['id'])
        ids['europe_pmc'] = raw['source'] + ':' + source_id
        if raw['source'] == 'MED':
            ids['pmid'] = source_id
        if raw.get('doi'):
            ids['doi'] = raw['doi']
        if raw.get('pmcid'):
            ids['pmcid'] = raw['pmcid']
        authors = [clean(a) for a in raw.get('authorString', '').rstrip('.').split(', ') if a]
        year = int(raw['pubYear']) if str(raw.get('pubYear', '')).isdigit() else None
        date, journal, kind = None, raw.get('journalAbbreviation'), raw.get('citationType')
        identifier = 'EPMC:' + ids['europe_pmc']
    if ids.get('doi'):
        ids['doi'] = re.sub(r'^https?://(?:dx\.)?doi.org/', '', ids['doi'], flags=re.I).lower()
    ev = raw.get('_metadata_evidence', raw['_evidence'])
    return {'id': identifier, 'identifiers': ids, 'title': clean(raw.get('title')) or 'Unknown title',
            'authors': authors, 'year': year, 'date': date, 'journal': journal, 'type': kind,
            'abstract': None, 'counts': {source: {'citations': raw.get('citedByCount')}},
            'provenance': [ev], 'conflicts': [], 'source_records': {source: raw}}


def merge_node(nodes, candidate, issues):
    """One agreeing persistent ID, no conflicting IDs, exactly one candidate match."""
    keys = ('openalex', 'doi', 'pmid', 'pmcid', 'europe_pmc')
    matching = [n for n in nodes.values() if any(n['identifiers'].get(k) == candidate['identifiers'].get(k)
                 for k in keys if candidate['identifiers'].get(k))]
    if not matching:
        nodes[candidate['id']] = candidate
        return candidate['id']
    valid = [n for n in matching if not any(n['identifiers'][k] != candidate['identifiers'][k]
             for k in keys if k in n['identifiers'] and k in candidate['identifiers'])]
    if len(matching) != 1 or len(valid) != 1:
        issues.append({'kind': 'identifier_conflict', 'candidate': candidate['id'], 'matches': [n['id'] for n in matching]})
        if candidate['id'] not in nodes:
            nodes[candidate['id']] = candidate
        else:
            nodes[candidate['id']]['conflicts'].append(candidate)
        return candidate['id']
    node = valid[0]
    for key in ('title', 'year'):
        if node.get(key) and candidate.get(key) and node[key] != candidate[key]:
            node['conflicts'].append({'field': key, 'value': candidate[key], 'sources': list(candidate['source_records'])})
    node['identifiers'].update(candidate['identifiers'])
    node['source_records'].update(candidate['source_records'])
    node['counts'].update(candidate['counts'])
    node['provenance'].extend(p for p in candidate['provenance'] if p not in node['provenance'])
    return node['id']


def discover(sources, seed, limit, issues):
    nodes, evidence, reports = {}, {}, []
    ids = seed['identifiers']
    queries = [('OpenAlex', sources.citations, ids['openalex'])]
    if ids.get('pmid'):
        queries += [('Europe PMC', sources.europe_citations, ids['pmid']), ('PubMed', sources.pubmed_citations, ids['pmid'])]
    else:
        reports.extend({'source': source, 'status': 'not queried: no PMID'} for source in ('Europe PMC', 'PubMed'))
    for source, method, identifier in queries:
        try:
            records, report, total = method(identifier, limit)
            report = {**report, 'source': source, 'available': total, 'retrieved': len(records),
                      'limit_per_source': limit, 'status': 'partial' if report.get('error') or total is None or len(records) < total else 'returned all indexed links'}
            reports.append(report)
            if report['status'] == 'partial':
                issues.append({'kind': 'citing_subset', **report})
            for raw in records:
                ev = raw.get('_evidence', report)
                try:
                    candidate = normalize(raw, ev) if source == 'OpenAlex' else biomedical_node(raw, source)
                    node_id = merge_node(nodes, candidate, issues)
                    evidence.setdefault(node_id, [])
                    if ev not in evidence[node_id]:
                        evidence[node_id].append(ev)
                except (ValueError, KeyError, TypeError) as exc:
                    issues.append({'kind': 'invalid_citing_record', 'source': source, 'id': raw.get('id'), 'detail': str(exc)})
        except APIError as exc:
            reports.append({'source': source, 'status': 'failed', 'error': str(exc), 'retrieved': 0})
            issues.append({'kind': 'citations_failed', 'source': source, 'detail': str(exc)})
    return nodes, evidence, reports


def citing_rows(result, query='', author_group='All'):
    evidence = {e['citing']: e['provenance'] for e in result['edges'] if e['cited'] == result['manifest']['seed']}
    rows = []
    for node in result['nodes']:
        if node['id'] not in evidence or node['id'] == result['manifest']['seed']:
            continue
        if query.casefold() not in ' '.join([node['title'], node.get('abstract') or '', *node['authors']]).casefold():
            continue
        group = node['analysis'].get('author_group', 'No match')
        if author_group != 'All' and group != author_group:
            continue
        ids = node['identifiers']
        url = ('https://doi.org/' + quote(ids['doi'], safe='/') if ids.get('doi') else
               'https://pubmed.ncbi.nlm.nih.gov/' + ids['pmid'] + '/' if ids.get('pmid') else
               'https://europepmc.org/article/' + ids['europe_pmc'].replace(':', '/') if ids.get('europe_pmc') else
               'https://openalex.org/' + ids['openalex'])
        rows.append({'id': node['id'], 'year': node['year'], 'title': node['title'], 'authors': '; '.join(node['authors']),
                     'sources': ', '.join(sorted({p['source'] for p in evidence[node['id']]})), 'author_match': group,
                     'doi': ids.get('doi'), 'pmid': ids.get('pmid'), 'url': url})
    return sorted(rows, key=lambda r: (r['year'] is None, -(r['year'] or 0), r['title']))
