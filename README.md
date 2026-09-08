![License](https://img.shields.io/badge/license-MIT%20%2B%20IP%20carve--out-blue)
![Python](https://img.shields.io/badge/python-3.13%2B-blue)
![MCP](https://img.shields.io/badge/MCP-FastMCP%204.0-purple)
![Datasets](https://img.shields.io/badge/datasets-7-green)
![Observations](https://img.shields.io/badge/IRENA%20observations-196k-green)
![Status](https://img.shields.io/badge/status-pre--release-orange)

# SparkScout MCP

Renewable energy data for AI assistants, with the source attached.

> [!IMPORTANT]
> **Project status: pre-release, single-operator deployment.** The repository contains the source code and the public documentation; the live MCP endpoint is not yet open for general registration. The Quickstart below gets you a working instance in five commands. The Status section further down sets out what the corpus covers today, what is not yet covered, and what to expect from the next refresh.
>
> The seven statistical datasets and the publication corpus are governed by the upstream publisher's terms of use; see `NOTICE` for attribution and reuse rules.

---

## Why this exists

Most AI assistants answer questions about renewable energy by recalling what they read during training. That works for general background and not for the kind of question where the answer has to be defensible: briefings that will be reviewed, policy notes that will be cited, investment memos that will be challenged, technical answers for analysts who can pull the source up.

SparkScout closes that gap. It gives the assistant a thin interface to a curated corpus: published reports from a reputable international organisation, and a set of structured statistical tables with country, technology, year, and investment dimensions. Every response carries the citation needed to trace the answer back to the source. The trade is small: the assistant has to call a tool, and the corpus has to be refreshed periodically from upstream.

---

## What it does

The server exposes 11 MCP tools over two backends. A natural-language question can be answered end to end: search the report corpus, retrieve a chapter, surface the dataset that holds the quantitative answer, and return both with citations. The same tools also serve quick factual queries: "What is Brazil's hydro capacity?", "How fast is solar power growing in West Africa?", "Which countries received the most public investment for renewable energy between 2010 and 2020?".

The corpus at this revision holds 56 publications and 7 statistical datasets (196,314 rows) covering power capacity, electricity generation, renewable energy shares, heat generation, and public finance flows.

---

## Status of the corpus

The numbers below are pulled live from the DuckDB snapshot at the time of this revision (2026-09-08). Run `sparkscout_list_datasets` against the running server to refresh after pulling a new snapshot.

### Statistical datasets

| Dataset | Rows | Year range | Units | Dimensions |
|---|---|---|---|---|
| `country_capacity` | 73,432 | 2000-2025 | MW | country, technology, grid connection, year |
| `country_generation` | 87,256 | 2000-2024 | GWh | country, technology, data type, grid connection, year |
| `region_capacity` | 4,399 | 2000-2025 | MW | region, technology, grid connection, year |
| `region_generation` | 2,615 | 2000-2024 | GWh | region, technology, data type, year |
| `re_share` | 10,826 | 2000-2025 | percent | region/country, indicator, year |
| `heat_generation` | 9,708 | 2000-2024 | TJ | country, technology, grid connection, year |
| `public_investments` | 8,078 | 2001-2023 | Million USD (2022 prices) | country, technology, year |

### Publications

56 markdown reports indexed. Energy transition outlooks, technology briefings (solar, wind, hydrogen, storage), regional analyses, policy briefs. Year, ISBN, and citation are extracted from each report's frontmatter.

### Covered today

- Installed power generation capacity and electricity generation by country and technology.
- Renewable share of capacity and generation.
- Heat generation by country and technology.
- Public financial flows for renewable energy by recipient country and technology.
- Full-text search across the indexed publication corpus, with chapter-level retrieval and citation.

### Not covered yet

- **Cost data** (LCOE, capex, opex, levelised cost of storage). The upstream source publishes these as separate datasets; they are not in the current DuckDB snapshot.
- **Project-level data** (individual power plants, project pipelines, financial deals). The current datasets are aggregate country and region views.
- **Sub-annual granularity**. All datasets report on an annual basis; quarterly and monthly series are not in scope.
- **Non-energy mitigation topics** (land use, water use, emissions factors). These live outside the energy statistics series.
- **Live network access**. The MCP endpoint is not yet registered publicly; the Quickstart runs the server locally.

---

## PxWeb to DuckDB ingestion

The seven statistical datasets are sourced from the IRENA Statistics PxWeb API (`https://pxweb.irena.org/api/v1/en/IRENASTAT`) and persisted to a single read-only DuckDB file at `data/irena/irena.duckdb`. The ingestion script is not shipped in this repository; it lives at `/home/simon/irena-data/crawl.py` on the host that owns the DuckDB file, and is invoked manually or by cron to refresh the snapshot. The MCP server reads the DuckDB file as-is and never executes the crawler.

### Pipeline shape

```
  PxWeb API          PxWeb API          DuckDB file (read-only)
  (metadata)         (chunked POST)     irena.duckdb
       │                   │                   │
       └──── crawl.py ─────┴──── atomic ──────►│
            (per-table)        os.replace       └──── app/tools/datasets.py
```

The crawler performs one metadata fetch per table (declaring dimension codes, label arrays, and the measure column) followed by a sequence of chunked data POSTs. Each table is written to a fresh DuckDB connection (`irena.duckdb.tmp`); on success, the temporary file replaces the live snapshot via `os.replace`, giving an atomic swap that the running MCP server observes on the next query without an explicit reload.

The MCP server's FTS5 report index is rebuilt independently, on container start or on `SIGHUP`. The DuckDB file itself is reopened lazily; no server restart is required after a successful crawl.

### Schema layout

For each fact table `T`, the crawler writes one main table plus one dimension table per dimension:

```sql
-- One main table per fact
CREATE TABLE T (
    <dim_1_code>  VARCHAR,
    <dim_2_code>  VARCHAR,
    ...,
    <measure_col> DOUBLE,    -- last column of PxWeb's data response
    source        VARCHAR    -- verbatim attribution from metadata[0].source
);

-- One dim table per dimension, code + label
CREATE TABLE dim_T_<dim> (
    code  VARCHAR PRIMARY KEY,
    label VARCHAR
);
```

Dimension table names are derived from the dimension code lowercased with `/` and space replaced by underscore (`Country/area` becomes `country_area`). The full set after a complete crawl is 7 fact tables and 27 dimension tables.

### Chunking

The PxWeb API rejects full-filter POSTs with HTTP 404 once the request body exceeds approximately 2 KB. The crawler works around this by chunking along the largest non-year dimension, in groups of 50 values, with the remaining dimensions requested as explicit full lists. A chunk that still 404s is halved and retried; if a single-cell query still fails, the values are fetched one at a time. Each successful POST carries an exponential backoff on HTTP 429 (rate-limited) and a 3-second retry on HTTP 5xx.

This strategy is verified against all seven tables in `devops/lxc-104-self-hosted-app/references/pxweb-api-cookbook-2026-09-07.md`. The cookbook is the canonical reference for the API surface, the verified table paths, the metadata schema, and the per-table quirks (user-agent requirement, body-cap cascade, singleton dimensions, source attribution format).

### Cardinality and sparsity

The DuckDB holds every cell IRENA publishes and nothing else. PxWeb returns sparse JSON: cells for which IRENA has no value are absent from the response payload, not encoded as null. The crawler performs a lossless pass-through of the response, so the resulting DuckDB is sparse to the same degree as the upstream publication.

| Fact table | Rows in DuckDB | Cartesian space (dim-product) | Fill rate |
|---|---|---|---|
| `country_capacity` | 73,432 | 305,552 (226 countries x 26 techs x 2 grids x 26 years) | 24.0% |
| `country_generation` | 87,256 | 338,688 (224 x 21 x 1 x 3 x 24) | 25.8% |
| `region_capacity` | 4,399 | 6,760 (10 x 13 x 2 x 26) | 65.1% |
| `region_generation` | 2,615 | 2,880 (10 x 12 x 1 x 24) | 90.8% |
| `re_share` | 10,826 | 12,116 (233 x 2 x 26) | 89.4% |
| `heat_generation` | 9,708 | 32,448 (52 x 13 x 2 x 24) | 29.9% |
| `public_investments` | 8,078 | 110,952 (201 x 23 x 24) | 7.3% |
| **Total** | **196,314** | **809,396** | **24.2%** |

The cartesian-space column is the size of the dimension cross-product, not a row count. Numbers in the older `pxweb-api-cookbook-2026-09-07.md` revisions labelled these values as "rows after crawl"; that label was incorrect and has been corrected. Maintainers extending the server, comparing snapshots, or quoting corpus sizes should use the row-count column.

### Year dim encoding

The PxWeb API exposes year as an index-based code (`'0'`, `'1'`, ..., `'25'`) with a parallel label array (`'2000'`, `'2001'`, ..., `'2025'`). The crawler preserves the encoding as-is: the fact-table year column contains the index string, the dim table holds both columns. Any query that needs the calendar year must join on the dim label, not the code.

### Source attribution

Each fact row carries a `source` column populated with the verbatim attribution string from PxWeb's `metadata[0].source` (for example, `"IRENA (2026), Renewable Capacity Statistics 2026, International Renewable Energy Agency (IRENA), Abu Dhabi"`). The MCP `DatasetResult.source` field surfaces this string to the client. The string identifies the vintage of the data; refreshing the corpus overwrites the column with the new vintage's attribution.

### Operational notes for maintainers

- **Re-running the crawler is idempotent on the file but not on the host filesystem.** Each run replaces `irena.duckdb` atomically via `os.replace` and writes a `manifest.json` summarising per-table row counts and the pull timestamp. Inspect the manifest after a run to confirm that all seven tables refreshed successfully.
- **Adding a new PxWeb table** requires editing the `TABLES` tuple list in `crawl.py` with the dataset name, the PxWeb path, the chunk dimension code, and the chunk size. No DuckDB schema work is required: the crawler builds the table and its dim tables dynamically from the API metadata.
- **The MCP server is read-only against the DuckDB file.** It opens the file with `read_only=True` and never writes. A concurrent crawl that swaps the file via `os.replace` is safe; the running server holds an open file descriptor to the old inode until its next query, which then transparently opens the new file.
- **Cross-checking the corpus.** The verification trace at `devops/sparkscout-mcp/references/sparkscout-pxweb-duckdb-full-document-verification-2026-09-08.md` documents the row counts, dim cardinalities, and cartesian-space calculations shown above. That reference is the single source of truth for corpus density; the table in this README is a snapshot at the time of writing.

---

## Repository layout

```
sparkscout/
├── app/
│   ├── Dockerfile             Python 3.13-slim, runs under uv
│   ├── fastmcp.json           FastMCP runtime config
│   ├── server.py              Entry point, table schemas, SIGHUP reload
│   └── tools/
│       ├── datasets.py        6 dataset tools over DuckDB
│       ├── duckdb_loader.py   Read-only DuckDB connection manager
│       ├── fts5_index.py      In-memory SQLite FTS5 report index
│       ├── fusion.py          sparkscout_answer_question
│       └── reports.py         4 report tools
├── docker-compose.yml         Local stack
├── LICENSE                    MIT plus IP carve-out
├── NOTICE                     Third-party data attribution
└── .gitignore                 Excludes operator-only paths
```

## Tools

| Tool | Layer | Purpose |
|---|---|---|
| `sparkscout_list_reports` | reports | List publications in the corpus |
| `sparkscout_get_report` | reports | Fetch a report body or single chapter |
| `sparkscout_search_reports` | reports | BM25 full-text search across reports |
| `sparkscout_cite` | reports | Formatted citation string |
| `sparkscout_list_datasets` | datasets | List the 7 statistical datasets |
| `sparkscout_get_dataset_meta` | datasets | Schema and sample codes for one dataset |
| `sparkscout_query_dataset` | datasets | Filtered, parameterised query with citations |
| `sparkscout_query_dataset_aggregations` | datasets | Group-by with sum, avg, count, min, max |
| `sparkscout_get_dataset_value` | datasets | Convenience scalar lookup |
| `sparkscout_sample_dataset` | datasets | Random sample rows |
| `sparkscout_answer_question` | cross | Natural-language search plus dataset hints |

All 11 tools return JSON. Dataset responses include an inline citation block in the form `[data: <dataset_id>, rows=N, filter=...]`.

## Data path

```
              ┌────────────────────────┐
              │  MCP client (any host) │
              └──────────┬─────────────┘
                         │  HTTPS + Bearer
                         ▼
              ┌────────────────────────┐
              │  Reverse proxy + auth  │   (operator-only, not in this repo)
              └──────────┬─────────────┘
                         │
                         ▼
              ┌────────────────────────┐
              │  FastMCP HTTP transport│
              │  11 tools, SIGHUP-reload│
              └──┬──────────────────┬──┘
                 │                  │
       DuckDB ◄──┘                  └──► SQLite FTS5 (in-memory)
       /data/irena/irena.duckdb       /data/reports/*.md
       (read-only)                   (rebuilt on SIGHUP)
```

Two storage backends, both read-only at runtime. DuckDB serves the 7 statistical tables; the FTS5 index is rebuilt from the markdown folder on startup or on SIGHUP.

## Quickstart

Prerequisites: Python 3.13+, [uv](https://docs.astral.sh/uv/), DuckDB 1.1.3, FastMCP 4.0.0, the upstream DuckDB snapshot at `./data/irena/irena.duckdb`, and the report markdowns at `./data/reports/`.

```bash
git clone https://github.com/ElectrifySimon/sparkscout
cd sparkscout

mkdir -p data/irena data/reports
# cp /path/to/irena.duckdb data/irena/
# cp /path/to/reports/*.md data/reports/

export FASTMCP_BEARER=<your-token>   # optional: enable the auth verifier

uv run --with fastmcp==4.0.0 --with duckdb==1.1.3 python app/server.py

# In a second terminal, probe health:
curl http://127.0.0.1:8000/health
# {"service":"sparkscout","duckdb":"ok","fts5_documents":56,"timestamp":"..."}
```

The server binds to `0.0.0.0:8000`. The MCP client config for a live hosted endpoint is not yet published; deployment information will be added when public access is opened.

## Architecture choices

- SQL is built with parameter binding. Dataset identifiers and column names are whitelisted against the in-process `TABLE_SCHEMAS` map before any query is constructed; no string interpolation touches user input.
- The FTS5 index is in-memory and rebuilt on SIGHUP. A single SIGHUP to the process refreshes both DuckDB and the report index without dropping connections.
- The container runs with a read-only root filesystem. Writable state is confined to named tmpfs volumes for the `uv` cache.

## Tests

The repository ships with manual verification scripts under `references/sparkscout-debug-recipes-2026-09-07.md`. Automated tests are not yet wired. To run the existing verifiers:

```bash
docker exec sparkscout bash -c 'ls /tmp/qa_*.py /tmp/trace_*.py'
docker exec sparkscout bash -c 'uv run --with duckdb==1.1.3 python /tmp/qa_fix_k.py'
```

The `qa_fix_*.py` scripts cover the bug fixes shipped in the initial release: technology alias resolution, plural-safe dim table lookup, and natural-language question tokenisation.

## Known issues

- `sparkscout_search_reports` uses a phrase-quoted FTS5 query; multi-word natural-language questions work better through `sparkscout_answer_question`, which tokenises the question, drops stopwords, and OR-merges per-term BM25 hits.

## License

- SparkScout source code: see [LICENSE](./LICENSE). MIT with an appended clause covering intellectual property in upstream content.
- Retrieved data and report text: see [NOTICE](./NOTICE). The statistics and publication text returned by this server remain subject to the upstream publisher's terms of use.

## Acknowledgement

This server is a thin interface over publicly available renewable energy data. All statistical findings carry inline citations; all publication excerpts carry the original citation block. Reuse of retrieved content should preserve those citations.
