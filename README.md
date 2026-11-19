# RIDA Citation Explorer v0.3

[Open the hosted app](https://rida-citation-explorer.streamlit.app/)

Previously named RIDA Research Roots. The Python package and CLI command remain `research_roots` for compatibility.

## New in v0.3

- Citing studies are retrieved from **OpenAlex, Europe PMC and PubMed**, with up to 500 records per source. OpenAlex and Europe PMC are paginated; PubMed uses `pubmed_pubmed_citedin` plus batched summaries.
- Citing publications are added before reference expansion so the reference tree cannot consume their entire node budget.
- The **Citing studies** tab provides newest-year-first results, source labels, keyword and author-match filters, links, source coverage, and CSV download.
- Select **Color nodes by → First / last author** on the timeline to highlight matches to the seed's first/last authors. Colors are surname/first-initial hints, not verified identities or confirmed research groups. Only first/last positions are compared; middle authors are excluded. The seed remains a gold diamond.

## Find citing studies systematically

1. Enter a DOI, PMID, or OpenAlex Work ID. For biomedical papers, a resolved PMID enables all three sources.
2. Set **Citing publications per source** and **Maximum publications** high enough. Use reference depth zero if you only want forward citation discovery.
3. Build the lineage, then open **Citing studies**. Clear graph filters to see the entire retrieved set. Search titles/authors/available abstracts with terms such as `vector`, `chemoprevention`, or `stratification`.
4. Inspect **Source coverage** and **Evidence** for failures, partial pages, unresolved records or graph limits. A source returning all its indexed links is not proof of complete citation coverage.
5. Export the JSON/manifest and CSV. On a later date, enable **Refresh source data** and compare exports by persistent identifiers. The app does not automatically schedule searches or label a paper's citation intent.

PubMed is queried directly through [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/), not merely through Europe PMC. Its [Cited by list](https://pubmed.ncbi.nlm.nih.gov/help/#cited-by) combines publisher and NCBI data and may be incomplete. PubMed and Europe PMC overlap; counts must not be summed and agreement is not independent confirmation. Preprints and published versions remain separate.

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
- [Europe PMC](https://europepmc.org/RestfulWebService): seed metadata enrichment and direct citing records.
- [PubMed](https://pubmed.ncbi.nlm.nih.gov/): direct cited-by links and publication summaries. Requests are paced to under three per second within the application process; shared hosting IPs may still encounter rate limits.
- Set `OPENALEX_API_KEY` in the environment if needed. Basic keyless requests are supported; a free key increases the quota. No paid API or LLM is required. See [OpenAlex authentication](https://help.openalex.org/api/authentication/).
- Credentials never appear in exported URLs. Do not commit keys or `.env` files; `.env` is ignored but is not automatically loaded.
- HTTP timeout: 20 seconds per attempt; up to three attempts with bounded backoff for transient errors and rate limits. Session cache: one hour, with original timestamps retained. Use the refresh checkbox to bypass it.

## Capabilities and limitations

- Direct reference expansion to depth two, plus direct citing publications; bounded nodes, edges and per-work references.
- Source-specific counts, original source records, per-record and per-edge timestamps, identifier match methods, conflicting metadata and unresolved reference reports.
- Chronological network, year/direction/depth/type filters, unknown-year handling, shared ancestry and transparent subset-based indicators.
- CSV, JSON, Markdown, reproducibility manifest and standalone interactive HTML exports.
- Citing-source reconciliation requires an agreeing persistent identifier, no conflicting identifiers, and exactly one matching candidate. Title similarity is never used to merge papers. Ambiguous matches are retained separately and reported. Reference expansion still uses canonical OpenAlex IDs; a source-only citing node can remain separate from a later resolved reference if no common ID was initially available.
- Missing or partial citation coverage is unavoidable. Completeness is unknown. No graph links are invented from similarity, coupling or co-citation.
- Reference selection uses provider order. OpenAlex citing results use newest publication date, Europe PMC uses provider order, and PubMed selects descending PMID (not necessarily publication date). Results are displayed by year after union. Each source is capped at 500 and the graph has independent limits. All indicators depend on these bounds. Metadata can contain source errors or unusual chronology.
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

Publication selection for ambiguous search results; stronger retrieval snapshots and dependency locking; optional openly licensed citation-context retrieval; author identity matching by ORCID. Citation-context classification is not implemented and will not be inferred from the graph.
