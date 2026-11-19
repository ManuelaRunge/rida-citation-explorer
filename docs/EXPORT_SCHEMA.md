# Export schema 1.0

`lineage.json` is the canonical, lossless snapshot. Top-level keys:

- `manifest`: schema/application versions, UTC creation time, input, seed ID and identifiers, actual metadata sources, citation sources, graph settings, filters, edge direction, selection policy and completeness (`unknown`). Source retrieval times are attached to records and edges rather than replaced by the export time.
- `nodes`: unique `id` (OpenAlex short ID), `identifiers`, title, authors, nullable year/date/journal/type/abstract, source-specific counts, provenance, conflicts, original `source_records`, and analysis annotations.
- `edges`: `citing`, `cited`, `relationship=direct_citation`, `evidence=retrieved`, and provenance list. Endpoints always exist in nodes.
- `issues`: structured query failures, unresolved references and truncation reports. Their absence does not imply completeness.

`manifest.json` repeats the manifest. `nodes.csv` includes normalized metadata, analysis and provenance. `publications.csv` is a metadata subset. `edges.csv` includes direction and evidence. Nested CSV values are JSON strings; missing values are empty cells. CSV uses UTF-8 BOM and quotes potentially executable spreadsheet formulas with a leading apostrophe. JSON retains original values.

`summary.md` describes the subset and cautions. The UI ZIP additionally includes `network.html`, with Plotly embedded for offline viewing. CLI exports omit HTML so the core pipeline has no third-party dependencies.

Breaking field changes require a schema major version bump. Additional optional fields may be introduced compatibly. Consumers should ignore unknown keys.
