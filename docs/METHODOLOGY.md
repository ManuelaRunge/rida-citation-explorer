# Methodology

## Graph construction

Resolve the seed through an exact DOI, PMID, or OpenAlex ID. Enrich seed metadata from Europe PMC when an agreeing DOI or PMID is available. Reject enrichment if another persistent identifier conflicts; retain the conflict for inspection. Original source records are retained.

Traverse OpenAlex `referenced_works` breadth-first up to reference depth two. Repeated canonical IDs denote the same node. An edge points **citing → cited**. Edge provenance belongs to the source record containing the reference, not to the referenced publication's metadata request. Direct citing works are fetched separately through the OpenAlex `cites` filter. Reference depth zero disables reference expansion; the independent citing limit must also be zero to retrieve only the seed.

Bounds apply to reference list prefixes, nodes, edges and seed citing results. Failed references and truncation are recorded. A failed seed resolution stops the analysis; a failed optional query leaves a partial graph and a visible issue. Boundary nodes are not expanded and should not be interpreted as having no references. Cycles are permitted and traversal is guarded against revisits.

## Indicators

- **Reachable citing works:** unique other retrieved nodes with a directed path to the node; excludes the node itself even in a cycle.
- **Direct citing works:** number of distinct incoming neighbors in the retrieved graph.
- **Seed reference branches:** number of distinct direct seed references whose reachable reference sets contain the node (including the branch root).
- **Shared ancestor:** a non-seed node occurs in at least two such branch sets. This is an analysis annotation, never a fabricated citation edge.
- **Reference/citing depth:** shortest directed distance from the seed through outgoing/incoming edges respectively.

These are graph heuristics, not validated measures of foundational status, importance, endorsement, or intellectual influence. Indicators are computed on the retrieved graph before UI filters; filtered exports declare that scope. Raw source citation counts remain separate from retrieved-network counts.

## Chronology and reproducibility

Order publications by reported year. Unknown years remain null and use a separate labelled display column. A publication's date is not a date for an idea. Filters preserve only edges whose endpoints remain visible. Paths may disappear under filtering.

Exports contain source URLs, original retrieval timestamps, normalized and raw metadata, graph settings, application/schema versions, filter settings, issues, and source-specific counts. A fresh query may differ as databases update. The JSON snapshot records what was observed, not an assertion of complete coverage. OpenAlex and Europe PMC metadata agreement does not imply citation-edge agreement because only OpenAlex edges are currently queried.

## Experimental citation contexts

Europe PMC exposes openly available full-text XML for some publications. A future experiment can map JATS `xref` reference IDs to bibliography entries, retain the citing passage and original persistent link, and store article-level licensing information. Feasibility depends on full-text availability, reliable identifier mapping and permission to redistribute text. This is not implemented in v0.2. No LLM or automated citation-intent classification runs by default or in the current pipeline.
