from collections import deque
from dataclasses import asdict, dataclass

from . import __version__
from .api import Sources, APIError, now
from .metadata import normalize, reconcile


@dataclass
class Settings:
    depth: int = 2
    max_nodes: int = 80
    max_edges: int = 200
    references_per_work: int = 20
    citing_limit: int = 20

    def __post_init__(self):
        if not 0 <= self.depth <= 2:
            raise ValueError('Depth must be 0–2.')
        for name in ('max_nodes', 'max_edges', 'references_per_work'):
            if not 1 <= getattr(self, name) <= 1000:
                raise ValueError(f'{name} must be 1–1000.')
        if not 0 <= self.citing_limit <= 100:
            raise ValueError('Citing limit must be 0–100.')


def build(identifier, settings=None, sources=None):
    settings, sources = settings or Settings(), sources or Sources()
    nodes, edges, issues = {}, {}, []
    raw, evidence = sources.work(identifier)
    seed = normalize(raw, evidence)
    nodes[seed['id']] = seed
    seed_id = seed['id']
    ids = seed['identifiers']
    kind = 'pmid' if ids.get('pmid') else 'doi' if ids.get('doi') else None
    if kind:
        try:
            record, ev = sources.europe(kind, ids[kind])
            if record:
                reconcile(seed, record, ev)
        except (APIError, ValueError) as exc:
            issues.append({'kind': 'metadata_enrichment_failed', 'detail': str(exc)})

    def add_node(record, ev):
        node = normalize(record, ev)
        if node['id'] not in nodes:
            if len(nodes) >= settings.max_nodes:
                return None
            nodes[node['id']] = node
        return node['id']

    def add_edge(a, b, ev):
        key = (a, b)
        if key in edges:
            return True
        if len(edges) >= settings.max_edges:
            issues.append({'kind': 'edge_limit', 'citing': a, 'cited': b})
            return False
        edges[key] = {'citing': a, 'cited': b, 'relationship': 'direct_citation', 'evidence': 'retrieved', 'provenance': [dict(ev)]}
        return True

    queue = deque([(raw, evidence, 0)])
    expanded = set()
    while queue:
        parent, ev, depth = queue.popleft()
        parent_id = parent['id'].rsplit('/', 1)[-1]
        if depth >= settings.depth or parent_id in expanded:
            continue
        expanded.add(parent_id)
        refs = parent.get('referenced_works') or []
        if len(refs) > settings.references_per_work:
            issues.append({'kind': 'reference_limit', 'work': parent_id, 'omitted': len(refs) - settings.references_per_work})
        for ref in refs[:settings.references_per_work]:
            if len(edges) >= settings.max_edges:
                issues.append({'kind': 'edge_limit', 'work': parent_id})
                break
            ref_id = ref.rsplit('/', 1)[-1]
            if ref_id in nodes:
                add_edge(parent_id, ref_id, ev)
                continue
            if len(nodes) >= settings.max_nodes:
                issues.append({'kind': 'node_limit', 'work': parent_id, 'unresolved': ref})
                continue
            try:
                child, child_ev = sources.work(ref)
                child_id = add_node(child, child_ev)
                if child_id:
                    add_edge(parent_id, child_id, ev)
                    queue.append((child, child_ev, depth + 1))
            except (APIError, ValueError) as exc:
                issues.append({'kind': 'unresolved_reference', 'work': parent_id, 'reference': ref, 'detail': str(exc)})
    if settings.citing_limit:
        try:
            records, ev, total = sources.citations(seed_id, settings.citing_limit)
            if total is None or total > len(records):
                issues.append({'kind': 'citing_subset', 'available': total, 'retrieved': len(records)})
            for record in records[:settings.citing_limit]:
                if len(edges) >= settings.max_edges:
                    issues.append({'kind': 'edge_limit', 'direction': 'citing'})
                    break
                node_id = add_node(record, ev)
                if node_id:
                    add_edge(node_id, seed_id, ev)
                else:
                    issues.append({'kind': 'node_limit', 'direction': 'citing'})
        except APIError as exc:
            issues.append({'kind': 'citations_failed', 'detail': str(exc)})
    result = {'manifest': {'schema_version': '1.0', 'application_version': __version__, 'created_at': now(),
              'input': identifier, 'seed': seed_id, 'seed_identifiers': seed['identifiers'],
              'settings': asdict(settings), 'completeness': 'unknown',
              'sources': sorted({p['source'] for n in nodes.values() for p in n['provenance']}),
              'edge_direction': 'citing -> cited', 'filters': {},
              'citation_sources': ['OpenAlex'], 'selection': 'reference list order; citing works ascending publication date'},
              'nodes': list(nodes.values()), 'edges': list(edges.values()), 'issues': issues}
    from .analysis import annotate
    annotate(result)
    return result
