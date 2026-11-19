from .identifiers import parse_identifier


def normalize(raw, evidence):
    ids = {'openalex': raw['id'].rsplit('/', 1)[-1]}
    for kind in ('doi', 'pmid'):
        value = (raw.get('ids') or {}).get(kind) or raw.get(kind)
        if value:
            try:
                parsed_kind, parsed = parse_identifier(value)
                if parsed_kind == kind:
                    ids[kind] = parsed
            except ValueError:
                pass
    index = raw.get('abstract_inverted_index') or {}
    words = {position: word for word, positions in index.items() for position in positions}
    source = (raw.get('primary_location') or {}).get('source') or {}
    return {'id': ids['openalex'], 'identifiers': ids, 'title': raw.get('title') or 'Unknown title',
            'authors': [a.get('author', {}).get('display_name', 'Unknown') for a in raw.get('authorships', [])],
            'year': raw.get('publication_year'), 'date': raw.get('publication_date'),
            'journal': source.get('display_name'), 'type': raw.get('type'),
            'abstract': ' '.join(words[i] for i in sorted(words)) or None,
            'counts': {'OpenAlex': {'citations': raw.get('cited_by_count'), 'references': len(raw.get('referenced_works') or [])}},
            'provenance': [dict(evidence)], 'conflicts': [], 'source_records': {'OpenAlex': raw}}


def reconcile(node, record, evidence):
    """Never silently merge conflicting persistent identifiers."""
    incoming = {}
    if record.get('doi'):
        incoming['doi'] = parse_identifier(record['doi'])[1]
    if record.get('pmid'):
        incoming['pmid'] = str(record['pmid'])
    conflicts = [k for k, v in incoming.items() if k in node['identifiers'] and node['identifiers'][k] != v]
    if conflicts:
        node['conflicts'].append({'source': 'Europe PMC', 'fields': conflicts, 'record': record, 'provenance': evidence})
        return False
    if not any(node['identifiers'].get(k) == v for k, v in incoming.items()):
        return False
    for field, value in [('title', record.get('title')), ('year', int(record['pubYear']) if str(record.get('pubYear', '')).isdigit() else None)]:
        if value and node.get(field) and node[field] != value:
            node['conflicts'].append({'source': 'Europe PMC', 'field': field, 'value': value})
    node['identifiers'].update(incoming)
    node['source_records']['Europe PMC'] = record
    node['provenance'].append(evidence)
    node['counts']['Europe PMC'] = {'citations': record.get('citedByCount')}
    if not node.get('abstract'):
        node['abstract'] = record.get('abstractText')
    return True
