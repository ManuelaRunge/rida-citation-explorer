"""Bounded HTTP retrieval; cache retains original retrieval timestamps."""
import copy
import json
import os
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from .identifiers import parse_identifier


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
        headers = {'User-Agent': 'RIDA-Research-Roots/0.2', 'Accept': 'application/json'}
        key = os.environ.get('OPENALEX_API_KEY')
        if url.startswith('https://api.openalex.org/') and key:
            headers['Authorization'] = 'Bearer ' + key
        for attempt in range(self.attempts):
            try:
                with urlopen(Request(url, headers=headers), timeout=self.timeout) as response:
                    result = (json.load(response), {'url': url, 'retrieved_at': now()})
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
        data, evidence = self.client.get('https://api.openalex.org/works', {
            'filter': 'cites:' + work_id.rsplit('/', 1)[-1], 'per_page': min(limit, 100),
            'sort': 'publication_date:asc'})
        evidence.update(source='OpenAlex', matching_method='openalex')
        return data.get('results', []), evidence, data.get('meta', {}).get('count')

    def europe(self, kind, value):
        query = f'EXT_ID:{value} AND SRC:MED' if kind == 'pmid' else f'DOI:"{value}"'
        data, evidence = self.client.get('https://www.ebi.ac.uk/europepmc/webservices/rest/search', {
            'query': query, 'format': 'json', 'resultType': 'core', 'pageSize': 2})
        evidence.update(source='Europe PMC', matching_method=kind)
        records = data.get('resultList', {}).get('result', [])
        return (records[0] if len(records) == 1 else None), evidence
