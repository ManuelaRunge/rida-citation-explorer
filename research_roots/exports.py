import csv
import io
import json
import zipfile


def csv_bytes(rows, fields):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        values = {}
        for key in fields:
            value = row.get(key)
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
                value = "'" + value
            values[key] = value
        writer.writerow(values)
    return stream.getvalue().encode('utf-8-sig')


def export_files(result):
    dump = lambda value: json.dumps(value, indent=2, ensure_ascii=False).encode('utf-8')
    summary = (f"# Research Roots exploration\n\nSeed: {result['manifest']['seed']}\n\n"
               f"Publications: {len(result['nodes'])}; citation edges: {len(result['edges'])}.\n\n"
               "Edges point from citing to cited publications. Citation paths are not proof of intellectual influence. "
               "Completeness is unknown. Network indicators describe the retrieved subset only.\n\n"
               f"Retrieval issues: {len(result['issues'])}. See lineage.json for evidence and manifest.json for settings.\n")
    node_fields = ['id', 'identifiers', 'title', 'authors', 'year', 'date', 'journal', 'type', 'abstract', 'counts', 'analysis', 'provenance', 'conflicts']
    return {'lineage.json': dump(result), 'manifest.json': dump(result['manifest']),
            'nodes.csv': csv_bytes(result['nodes'], node_fields),
            'publications.csv': csv_bytes(result['nodes'], node_fields[:10] + ['counts', 'provenance']),
            'edges.csv': csv_bytes(result['edges'], ['citing', 'cited', 'relationship', 'evidence', 'provenance']),
            'summary.md': summary.encode('utf-8')}


def bundle(result, html=None):
    files = export_files(result)
    if html:
        files['network.html'] = html.encode('utf-8')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return stream.getvalue()
