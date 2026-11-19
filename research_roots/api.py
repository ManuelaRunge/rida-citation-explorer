"""Bounded HTTP retrieval; cache retains original retrieval timestamps."""
import copy
import json
import os
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from threading import Lock
from urllib.request import Request, urlopen

from .identifiers import parse_identifier

_ncbi_lock = Lock()
_ncbi_last_request = 0.0


def now():
    return datetime.now(timezone.utc).isoformat()


class APIError(RuntimeError):
    pass


class Client:
    def __init__(self, ttl=3600, timeout=20, attempts=3):
        self.ttl, self.timeout, self.attempts = ttl, timeout, attempts
        self.cache = {}

    def get(self, url, params=None):
        url += ('?' + urlencode(params)) if params else ''
        cached = self.cache.get(url)
        if cached and time.monotonic() - cached[0] < self.ttl:
            return copy.deepcopy(cached[1])
        headers = {'User-Agent': 'RIDA-Citation-Explorer/0.3', 'Accept': 'application/json'}
        key = os.environ.get('OPENALEX_API_KEY')
        if url.startswith('https://api.openalex.org/') and key:
            headers['Authorization'] = 'Bearer ' + key
        for attempt in range(self.attempts):
            try:
                if url.startswith('https://eutils.ncbi.nlm.nih.gov/'):
                    global _ncbi_last_request
                    with _ncbi_lock:
                        time.sleep(max(0, 0.4 - (time.monotonic() - _ncbi_last_request)))
                        _ncbi_last_request = time.monotonic()
                with urlopen(Request(url, headers=headers), timeout=self.timeout) as response:
                    result = (json.load(response), {'url': url, 'retrieved_at': now()})
                if isinstance(result[0], dict) and ('error' in result[0] or 'ERROR' in result[0]):
                    raise APIError('Source returned an API error from ' + url.split('?')[0])
                self.cache[url] = (time.monotonic(), result)
                return copy.deepcopy(result)
            except HTTPError as exc:
                retry = exc.code == 429 or exc.code >= 500
                delay = exc.headers.get('Retry-After', '') if exc.headers else ''
                delay = min(float(delay), 30) if delay.isdigit() else 2 ** attempt
                if not retry or attempt == self.attempts - 1:
                    raise APIError(f'HTTP {exc.code} from {url.split("?")[0]}') from None
            except (URLError, TimeoutError, OSError, ValueError):
                delay = 2 ** attempt
                if attempt == self.attempts - 1:
                    raise APIError(f'Unable to retrieve valid JSON from {url.split("?")[0]}') from None
            time.sleep(delay)


class Sources:
    def __init__(self, client=None):
        self.client = client or Client()

    def work(self, identifier):
        kind, value = parse_identifier(identifier)
        if kind == 'openalex':
            data, evidence = self.client.get('https://api.openalex.org/works/' + value)
        else:
            value = 'https://doi.org/' + value if kind == 'doi' else value
            data, evidence = self.client.get('https://api.openalex.org/works', {'filter': f'{kind}:{value}', 'per_page': 2})
            results = data.get('results', [])
            if len(results) != 1:
                raise APIError('Publication not found uniquely in OpenAlex.')
            data = results[0]
        evidence.update(source='OpenAlex', matching_method=kind)
        return data, evidence

    def citations(self, work_id, limit):
        return self._citation_pages('OpenAlex', 'https://api.openalex.org/works',
            {'filter': 'cites:' + work_id.rsplit('/', 1)[-1], 'sort': 'publication_date:desc'}, limit)

    def europe_citations(self, pmid, limit):
        return self._citation_pages('Europe PMC',
            f'https://www.ebi.ac.uk/europepmc/webservices/rest/MED/{pmid}/citations', {'format': 'json'}, limit)

    def _citation_pages(self, source, url, params, limit):
        records, seen, pages, total = [], set(), [], None
        report = {'source': source, 'pages': pages, 'selection': 'newest first' if source == 'OpenAlex' else 'provider order'}
        if limit <= 0:
            return records, report, total
        size = min(limit, 100)
        for page in range(1, (limit + size - 1) // size + 1):
            try:
                data, ev = self.client.get(url, {**params, 'page': page,
                    'per_page' if source == 'OpenAlex' else 'pageSize': size})
            except APIError as exc:
                report['error'] = str(exc)
                break
            ev.update(source=source, matching_method='source citation endpoint')
            pages.append(ev)
            batch = data.get('results', []) if source == 'OpenAlex' else data.get('citationList', {}).get('citation', [])
            total = data.get('meta', {}).get('count') if source == 'OpenAlex' else data.get('hitCount')
            added = 0
            for raw in batch:
                key = (raw.get('source', source), str(raw.get('id')))
                if key not in seen and len(records) < limit:
                    seen.add(key)
                    records.append({**raw, '_evidence': ev})
                    added += 1
            if not batch or (total is not None and page * size >= total):
                break
            if not added:
                report['error'] = 'Pagination returned no new records; stopped.'
                break
        return records, report, total

    def pubmed_citations(self, pmid, limit):
        base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
        data, ev = self.client.get(base + 'elink.fcgi', {'dbfrom': 'pubmed', 'db': 'pubmed',
            'id': pmid, 'linkname': 'pubmed_pubmed_citedin', 'retmode': 'json', 'tool': 'rida_research_roots'})
        if 'linksets' not in data or any('error' in group for group in data['linksets']):
            raise APIError('PubMed did not return a usable cited-by link response.')
        ev.update(source='PubMed', matching_method='pubmed_pubmed_citedin')
        ids = sorted({str(i) for group in data.get('linksets', []) for links in group.get('linksetdbs', [])
                      if links.get('linkname') == 'pubmed_pubmed_citedin' for i in links.get('links', [])}, key=int, reverse=True)
        report = {'source': 'PubMed', 'pages': [ev], 'selection': 'descending PMID (not publication date)'}
        records = []
        for start in range(0, min(limit, len(ids)), 100):
            selected = ids[start:min(start + 100, limit)]
            try:
                summaries, metadata_ev = self.client.get(base + 'esummary.fcgi', {
                    'db': 'pubmed', 'id': ','.join(selected), 'retmode': 'json', 'tool': 'rida_research_roots'})
                metadata_ev.update(source='PubMed', matching_method='pmid')
                values = summaries.get('result', {})
                for uid in selected:
                    if uid in values and 'error' not in values[uid]:
                        records.append({**values[uid], '_evidence': ev, '_metadata_evidence': metadata_ev})
                    else:
                        report['error'] = 'Some linked PMIDs had no usable metadata.'
            except APIError as exc:
                report['error'] = str(exc)
                break
        return records, report, len(ids)

    def europe(self, kind, value):
        query = f'EXT_ID:{value} AND SRC:MED' if kind == 'pmid' else f'DOI:"{value}"'
        data, evidence = self.client.get('https://www.ebi.ac.uk/europepmc/webservices/rest/search', {
            'query': query, 'format': 'json', 'resultType': 'core', 'pageSize': 2})
        evidence.update(source='Europe PMC', matching_method=kind)
        records = data.get('resultList', {}).get('result', [])
        return (records[0] if len(records) == 1 else None), evidence
