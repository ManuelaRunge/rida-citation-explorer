# RIDA Research Roots v0.2

A lightweight scientific citation-lineage explorer for individual researchers. Enter a DOI, PMID, or OpenAlex Work ID to trace references across up to two generations, inspect publications citing the seed, and explore publication chronology. Citation paths are bibliographic evidence, **not proof of intellectual influence**.

This repository was created from scratch after the selected workspace was found empty. No prior implementation was available to preserve.

## Run

Python 3.11 or newer:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Enter `35300707`, a DOI such as `10.1234/example` (replace with a real DOI), or an OpenAlex `W...` ID. Set retrieval limits, build the lineage, inspect evidence, then download the ZIP. The graph supports hover, zoom and pan; the inspection tab provides complete records and directed citation paths.

The command-line pipeline uses only the Python standard library:

```powershell
python -m research_roots 35300707 --depth 2 --max-nodes 80 --output output/example
```

## Sources and configuration

- [OpenAlex API](https://help.openalex.org/api/): publication resolution, source metadata, references and citing works.
- [Europe PMC](https://europepmc.org/RestfulWebService): seed metadata enrichment and identifier cross-check. It is not currently a second citation-graph source.
- Set `OPENALEX_API_KEY` in the environment if needed. Basic keyless requests are supported; a free key increases the quota. No paid API or LLM is required. See [OpenAlex authentication](https://help.openalex.org/api/authentication/).
- Credentials never appear in exported URLs. Do not commit keys or `.env` files; `.env` is ignored but is not automatically loaded.
- HTTP timeout: 20 seconds per attempt; up to three attempts with bounded backoff for transient errors and rate limits. Session cache: one hour, with original timestamps retained. Use the refresh checkbox to bypass it.

## Capabilities and limitations

- Direct reference expansion to depth two, plus direct citing publications; bounded nodes, edges and per-work references.
- Source-specific counts, original source records, per-record and per-edge timestamps, identifier match methods, conflicting metadata and unresolved reference reports.
- Chronological network, year/direction/depth/type filters, unknown-year handling, shared ancestry and transparent subset-based indicators.
- CSV, JSON, Markdown, reproducibility manifest and standalone interactive HTML exports.
- Identity is based on canonical OpenAlex IDs; Europe PMC metadata is merged only on an agreeing persistent identifier with no conflicting identifiers. Title similarity is never used to merge papers. Distinct OpenAlex records sharing a DOI are retained separately rather than guessed to be identical.
- Missing or partial citation coverage is unavoidable. Completeness is unknown. No graph links are invented from similarity, coupling or co-citation.
- Reference selection uses provider order. Citing results use earliest publication date, up to 100 works; there is no exhaustive pagination. All indicators depend on these limits. Metadata can contain source errors or unusual chronology.
- A seed must resolve uniquely in OpenAlex. Europe PMC enriches the seed, but cannot currently substitute for a missing OpenAlex seed.
- UI dependency versions are bounded by major version rather than fully locked. The manifest captures the application version and analysis settings; identical future API responses cannot be guaranteed. Archive the exported JSON to preserve the observed evidence.

See [methodology](docs/METHODOLOGY.md) and [export schema](docs/EXPORT_SCHEMA.md).

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests use synthetic source records and mocked HTTP responses, without live APIs. To run the optional PMID 35300707 integration smoke test:

```powershell
$env:RESEARCH_ROOTS_LIVE = '1'
python -m unittest discover -s tests -p test_live.py -v
```

## Planned work

Europe PMC citation-edge reconciliation; publication selection for ambiguous search results; stronger retrieval snapshots and dependency locking; optional openly licensed citation-context retrieval. Citation-context classification is not implemented and will not be inferred from the graph.
