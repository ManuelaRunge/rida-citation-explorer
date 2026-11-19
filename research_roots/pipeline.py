from collections import deque
from dataclasses import asdict, dataclass

from . import __version__
from .api import Sources, APIError, now
from .metadata import normalize, reconcile
from .citations import discover


@dataclass
class Settings:
    depth: int = 2
    max_nodes: int = 200
    max_edges: int = 200
    references_per_work: int = 20
    citing_limit: int = 100

    def __post_init__(self):
        if not 0 <= self.depth <= 2:
            raise ValueError('Depth must be 0–2.')
        for name in ('max_nodes', 'max_edges', 'references_per_work'):
            if not 1 <= getattr(self, name) <= 1000:
                raise ValueError(f'{name} must be 1–1000.')
        if not 0 <= self.citing_limit <= 500:
            raise ValueError('Citing limit must be 0–500 per source.')


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
            if ev not in edges[key]['provenance']:
                edges[key]['provenance'].append(dict(ev))
            return True
        if len(edges) >= settings.max_edges:
            issues.append({'kind': 'edge_limit', 'citing': a, 'cited': b})
            return False
        edges[key] = {'citing': a, 'cited': b, 'relationship': 'direct_citation', 'evidence': 'retrieved', 'provenance': [dict(ev)]}
        return True

    citation_reports = []
    if settings.citing_limit:
        citing_nodes, citing_evidence, citation_reports = discover(sources, seed, settings.citing_limit, issues)
        ordered = sorted(citing_nodes.values(), key=lambda n: (n['year'] is None, -(n['year'] or 0), n['id']))
        omitted = 0
        for node in ordered:
            if node['id'] == seed_id:
                continue
            if len(nodes) >= settings.max_nodes or len(edges) >= settings.max_edges:
                omitted += 1
                continue
            nodes[node['id']] = node
            for ev in citing_evidence[node['id']]:
                add_edge(node['id'], seed_id, ev)
        if omitted:
            issues.append({'kind': 'citing_graph_limit', 'omitted': omitted})

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
                existing = nodes[ref_id]['source_records'].get('OpenAlex')
                if existing:
                    queue.append((existing, nodes[ref_id]['provenance'][0], depth + 1))
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
    result = {'manifest': {'schema_version': '2.0', 'application_version': __version__, 'created_at': now(),
              'input': identifier, 'seed': seed_id, 'seed_identifiers': seed['identifiers'],
              'settings': asdict(settings), 'completeness': 'unknown',
              'sources': sorted({p['source'] for n in nodes.values() for p in n['provenance']}),
              'edge_direction': 'citing -> cited', 'filters': {},
              'citation_sources': sorted({p['source'] for e in edges.values() for p in e['provenance']}),
              'citation_retrieval': citation_reports,
              'selection': 'citers first, newest year first after source union; references in provider order'},
              'nodes': list(nodes.values()), 'edges': list(edges.values()), 'issues': issues}
    from .analysis import annotate
    annotate(result)
    return result
