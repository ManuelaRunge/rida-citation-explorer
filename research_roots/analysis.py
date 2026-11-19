from collections import deque
from copy import deepcopy
import re
import unicodedata


def author_key(name):
    """Conservative surname/first-initial hint; never a verified person/group ID."""
    text = ''.join(c for c in unicodedata.normalize('NFKD', name) if not unicodedata.combining(c))
    parts = re.findall(r'[A-Za-z]+', text)
    if len(parts) < 2:
        return None
    if len(parts[-1]) <= 3 and parts[-1].isupper():
        return (''.join(parts[:-1]).casefold(), parts[-1][0].casefold())
    return (parts[-1].casefold(), parts[0][0].casefold())


def author_group(seed, node):
    if node['id'] == seed['id']:
        return 'Seed'
    a, b = seed.get('authors') or [], node.get('authors') or []
    if not a or not b:
        return 'Unknown authors'
    endpoints = {author_key(b[0]), author_key(b[-1])} - {None}
    first, last = author_key(a[0]), author_key(a[-1])
    if first in endpoints and last in endpoints and first != last:
        return 'Both seed authors'
    if first and first in endpoints:
        return 'Seed first author'
    if last and last in endpoints:
        return 'Seed last author'
    return 'No match'


def distances(start, adjacency):
    found, queue = {start: 0}, deque([start])
    while queue:
        current = queue.popleft()
        for neighbor in sorted(adjacency.get(current, [])):
            if neighbor not in found:
                found[neighbor] = found[current] + 1
                queue.append(neighbor)
    return found


def annotate(result):
    outgoing, incoming = {}, {}
    for edge in result['edges']:
        outgoing.setdefault(edge['citing'], set()).add(edge['cited'])
        incoming.setdefault(edge['cited'], set()).add(edge['citing'])
    seed = result['manifest']['seed']
    ancestry = distances(seed, outgoing)
    citing = distances(seed, incoming)
    branches = [distances(child, outgoing) for child in outgoing.get(seed, [])]
    seed_node = next(n for n in result['nodes'] if n['id'] == seed)
    for node in result['nodes']:
        identifier = node['id']
        shared = sum(identifier in branch for branch in branches)
        node['analysis'] = {
            'author_group': author_group(seed_node, node),
            'reference_depth': ancestry.get(identifier), 'citing_depth': citing.get(identifier),
            'role': 'seed' if identifier == seed else 'reference' if identifier in ancestry else 'citing',
            'reachable_citing_works': len(distances(identifier, incoming)) - 1,
            'direct_citing_works': len(incoming.get(identifier, [])),
            'seed_reference_branches': shared, 'shared_ancestor': shared >= 2 and identifier != seed}


def filter_graph(result, year_min=None, year_max=None, direction='all', depth=2, publication_type='all', include_unknown=True):
    result = deepcopy(result)
    def keep(n):
        a, year = n['analysis'], n['year']
        if year is None and not include_unknown:
            return False
        if year is not None and ((year_min is not None and year < year_min) or (year_max is not None and year > year_max)):
            return False
        if publication_type != 'all' and n.get('type') != publication_type:
            return False
        if a['role'] == 'seed':
            return True
        levels = [a.get('reference_depth')] if direction == 'references' else [a.get('citing_depth')] if direction == 'citing' else [a.get('reference_depth'), a.get('citing_depth')]
        return any(d is not None and d <= depth for d in levels)
    result['nodes'] = [n for n in result['nodes'] if keep(n)]
    kept = {n['id'] for n in result['nodes']}
    result['edges'] = [e for e in result['edges'] if e['citing'] in kept and e['cited'] in kept]
    result['manifest']['filters'] = dict(year_min=year_min, year_max=year_max, direction=direction, depth=depth,
                                       publication_type=publication_type, include_unknown=include_unknown)
    result['manifest']['indicator_scope'] = 'full retrieved graph before display filters'
    return result


def citation_path(result, start, end):
    adjacency = {}
    for e in result['edges']:
        adjacency.setdefault(e['citing'], []).append(e['cited'])
    queue, visited = deque([(start, [start])]), {start}
    while queue:
        current, path = queue.popleft()
        if current == end:
            return path
        for nxt in adjacency.get(current, []):
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, path + [nxt]))
    return []
