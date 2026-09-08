![License](https://img.shields.io/badge/license-MIT%20%2B%20IP%20carve--out-blue)
![Python](https://img.shields.io/badge/python-3.13%2B-blue)
![MCP](https://img.shields.io/badge/MCP-FastMCP%204.0-purple)
![Datasets](https://img.shields.io/badge/datasets-7-green)
![Observations](https://img.shields.io/badge/IRENA%20observations-196k-green)
![Status](https://img.shields.io/badge/status-pre--release-orange)

# ✨ SparkScout MCP

Renewable energy data for AI assistants, with the source attached.

> [!IMPORTANT]
> **Project status: pre-release, single-operator deployment.** The repository contains the source code and the public documentation; the live MCP endpoint is not yet open for general registration. The Quickstart below gets you a working instance in five commands. The Status section further down sets out what the corpus covers today, what is not yet covered, and what to expect from the next refresh.
>
> The seven statistical datasets and the publication corpus are governed by the upstream publisher's terms of use; see `NOTICE` for attribution and reuse rules.

---

## 🧭 Non-Technical Overview

SparkScout is a question-answering service for renewable energy. You ask it a question about solar power, wind power, hydro, heat, electricity generation, public investment in renewable energy, or one of the major country or regional reports from a reputable IGO, and it gives you an attributed answer drawn from that this IGO's published data and reports. Every figure it returns is tagged with the publication or dataset the figure came from, so you can verify it against the source.

The service is meant for situations where the answer has to be defensible: briefings that will be reviewed, policy notes that will be cited, investment memos that will be challenged, technical answers for analysts who will pull the original up. The trade is small on your end: the answer comes with the citation, and the citation is what makes the answer usable.

Examples of questions the service can answer:

- What was Brazil's installed solar capacity in 2024?
- How fast has wind power grown in West Africa over the last decade?
- Which countries received the most public investment for renewable energy between 2010 and 2020?
- What does the most recent renewable capacity statistics report say about capacity additions in 2024?
- Which report covers geothermal heat generation in East Africa, and what is its main finding?

The rest of this document explains the system in technical terms: the data sources, the ingestion pipeline, the corpus coverage, the architecture, and how to run a local instance. Read on if any of that is relevant to what you need to do. If you only need the answer to a question, you do not need anything below this section; the citation comes back with the answer.

---

## ▶️ How to use it

If you are talking to an AI assistant, you do not interact with SparkScout directly. You ask a question about renewable energy, the assistant calls SparkScout on your behalf, and the answer comes back with a citation you can verify against the source. Ask the assistant *What was Brazil's installed solar capacity in 2024?* for a number from a statistical dataset, or *Which countries received the most public investment for renewable energy between 2010 and 2020?* for a country ranking with a link to the underlying publication. The citation is what makes the answer usable.

If your assistant has not been configured to know about this server, the operator deploys the local instance following the *Quickstart* below and gives you a bearer token. You then follow the per-client setup in `docs/integrate.md` to wire the assistant to the live service. That doc covers Claude Desktop, Claude Code, Cursor, Cline, Continue, and direct API access, with the copy-pasteable config blocks and the verification command. The *Data path* section below explains the three URL paths a client config can target.

## 🎯 Why this exists

Most AI assistants answer questions about renewable energy by recalling what they read during training. That works for general background and not for the kind of question where the answer has to be defensible: briefings that will be reviewed, policy notes that will be cited, investment memos that will be challenged, technical answers for analysts who can pull the source up.

SparkScout closes that gap. It gives the assistant a thin interface to a curated corpus: published reports from a reputable international organisation, and a set of structured statistical tables with country, technology, year, and investment dimensions. Every response carries the citation needed to trace the answer back to the source. The trade is small: the assistant has to call a tool, and the corpus has to be refreshed periodically from upstream.

---

## 🛠 What it does

The server exposes 11 MCP tools over two backends. A natural-language question can be answered end to end: search the report corpus, retrieve a chapter, surface the dataset that holds the quantitative answer, and return both with citations. The same tools also serve quick factual queries: "What is Brazil's hydro capacity?", "How fast is solar power growing in West Africa?", "Which countries received the most public investment for renewable energy between 2010 and 2020?".

The corpus at this revision holds 56 publications and 7 statistical datasets (196,314 rows) covering power capacity, electricity generation, renewable energy shares, heat generation, and public finance flows.

---

## 📊 Status of the corpus

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

## 🔌 PxWeb to DuckDB ingestion

The seven statistical datasets are sourced from the IRENA Statistics PxWeb API (`https://pxweb.irena.org/api/v1/en/IRENASTAT`) and persisted to a single read-only DuckDB file at `data/irena/irena.duckdb`. The ingestion script is not part of this repository; it runs out of band on the operator's host and is invoked manually or by cron to refresh the snapshot. The MCP server reads the DuckDB file as-is and never executes the crawler.

### Pipeline shape

```
  PxWeb API          PxWeb API          DuckDB file (read-only)
  (metadata)         (chunked POST)     irena.duckdb
       │                   │                   │
       └─ operator's ──────┴──── atomic ──────►│
            crawler          os.replace       └─► app/tools/datasets.py
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

This strategy is verified against all seven tables. The operator maintains a separate cookbook reference documenting the API surface, the verified table paths, the metadata schema, and the per-table quirks (user-agent requirement, body-cap cascade, singleton dimensions, source attribution format).

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
- **Adding a new PxWeb table** requires editing the operator's crawler configuration with the dataset name, the PxWeb path, the chunk dimension code, and the chunk size. No DuckDB schema work is required: the crawler builds the table and its dim tables dynamically from the API metadata.
- **The MCP server is read-only against the DuckDB file.** It opens the file with `read_only=True` and never writes. A concurrent crawl that swaps the file via `os.replace` is safe; the running server holds an open file descriptor to the old inode until its next query, which then transparently opens the new file.
- **Cross-checking the corpus.** The fill rates and cartesian-space denominators in the table above are derived from the live DuckDB snapshot; they are reproducible by counting rows in each fact table and multiplying the cardinalities of its dimension tables.

---

## 📄 Markdown report ingestion

The publication half of the corpus is a flat directory of Markdown files at `data/reports/`. Each file is one IRENA publication: front matter, body, figures described in text. The MCP server treats the directory as the source of truth and rebuilds an in-memory full-text index from it on every container start and on `SIGHUP`. No external database is involved for the report half; the index lives in SQLite's FTS5 engine, scoped to the process lifetime, and is rebuilt from disk on each refresh rather than incrementally updated.

### Why Markdown and not PDF

The corpus is served to the model as text, not as binary. PDFs are difficult for retrieval-grade models to consume directly: scanned pages, multi-column layouts, embedded figure captions, and the absence of structural cues all degrade the signal that a BM25 retriever or a downstream LLM can act on. The convention here is that every publication is converted to Markdown before it lands in `data/reports/`. Markdown preserves the document's heading hierarchy, table structure, and inline emphasis as plain text that the indexer can tokenise; it discards the visual layout, which is irrelevant to retrieval.

### Schema

The FTS5 virtual table is built once per refresh:

```sql
CREATE VIRTUAL TABLE reports_fts USING fts5(
    report_id UNINDEXED,
    content,
    tokenize = 'porter unicode61'
);
```

`report_id` is the filename without the `.md` extension, used as a stable lookup key across the four report tools and the dataset fusion layer. `content` is the entire file body as a single string. The tokeniser is the FTS5 built-in `porter unicode61`, which combines Porter stemming with Unicode-aware case folding. No custom tokeniser, no stopword list, no synonyms table.

In parallel, the builder walks the same directory once and extracts a small metadata record per file, held in a process-local dict keyed by `report_id`:

| Field | Source |
|---|---|
| `title` | First `# H1` heading in the file, falling back to the first non-empty line if no H1 is present |
| `year` | First `© IRENA YYYY` substring |
| `isbn` | First `ISBN: …` line |
| `citation` | First `Citation: …` line |
| `file_path` | Absolute path to the `.md` file, for chapter retrieval and debug |

The metadata record is not stored in FTS5; it is recomputed on every refresh and held in memory. FTS5 carries only the searchable content. The four report tools (`sparkscout_list_reports`, `sparkscout_get_report`, `sparkscout_search_reports`, `sparkscout_cite`) read the in-memory metadata dict and the FTS5 table in lockstep.

### What the indexer expects from each file

A file in `data/reports/` is consumable if and only if it satisfies three conditions:

1. It is valid UTF-8 (or reads cleanly with the `errors="replace"` fallback).
2. Its filename ends in `.md`.
3. It contains at least one heading or one non-empty line, so the metadata extractor has something to anchor on.

There is no YAML frontmatter requirement, no mandatory schema tag, and no minimum length. Files that fail to parse are logged at WARN level and skipped; the build proceeds over the remaining files. A corpus that is partially missing or partially malformed degrades gracefully rather than aborting the refresh.

The four metadata patterns (H1, copyright year, ISBN, citation) are conventional, not enforced. Files that lack a `© IRENA YYYY` substring return `year: null` from `sparkscout_list_reports` and are silently excluded from year-filtered listings. Files that lack a `Citation:` line fall back to a synthesised APA citation in `sparkscout_cite` (style `"apa"`).

### How chapter retrieval works

`sparkscout_get_report` accepts an optional `chapter` argument. The implementation resolves this by scanning the file body for an H2 heading that case-insensitively matches the requested chapter title, and returning everything from that heading to the next H2 or end of file:

```python
pattern = re.compile(
    r"^##\s+{title}.*?(?=^##\s|\Z)".format(title=re.escape(chapter)),
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
```

The regex anchors on H2 only. H3 and deeper are not chapter boundaries; they belong to the enclosing H2 chapter. A chapter argument that does not match any H2 in the file returns the full body, same as if no chapter was supplied.

The body is truncated at `max_chars` (default 50,000) with a `[truncated, full report is N chars]` marker appended. The full size is reported in `total_chars` so a downstream client can decide whether to re-fetch with a higher cap.

### Search behaviour

`sparkscout_search_reports` runs a BM25-ranked MATCH against the FTS5 table. The query is escaped to FTS5 MATCH syntax by wrapping multi-word queries in double quotes (a deliberate trade-off: phrase queries are precise on the literal text but brittle on natural-language rephrasings). The top-k hits (default 5, capped at 20) carry a 12-token snippet with `[` `]` as token delimiters and a BM25 score.

For natural-language questions, the fusion tool `sparkscout_answer_question` does not use `sparkscout_search_reports` directly; it tokenises the question, drops a small built-in English stopword set, OR-merges the remaining tokens against the FTS5 index, and de-duplicates hits by `report_id`. This produces broader recall at the cost of precision, which is the correct trade-off for open-ended questions.

### Refresh lifecycle

The FTS5 index is in-memory and rebuilt on:

- container start (initial `build()` call from the server entry point);
- `SIGHUP` (a process-level signal that the server handles by calling `build()` again).

The build is synchronous and walks the entire `data/reports/` directory; refresh time scales linearly with corpus size. There is no incremental update, no change detection, and no dirty-tracking. Adding, removing, or editing a Markdown file in `data/reports/` has no effect on the running server until the next SIGHUP (or a container restart).

The DuckDB half of the corpus is unaffected by the report refresh; the two backends are independent. SIGHUP refreshes only FTS5; the DuckDB file is read-only from the server's perspective and is replaced out-of-band by the operator's crawler.

### Operational notes for maintainers

- **Markdown is the contract.** A file in `data/reports/` is treated as the authoritative text for that publication. If the upstream PDF has figures, tables, or section structures that the Markdown does not preserve, the model's retrieval and citation will reflect only what the Markdown contains. The conversion step from PDF to Markdown is upstream of this repository; this server does not perform it.
- **Title and year are heuristics.** The extractor relies on patterns (`# H1`, `© IRENA YYYY`). If a publication's Markdown does not follow these patterns, the metadata fields will be empty and the corpus will be harder to navigate. Run `sparkscout_list_reports` after a refresh and check for empty titles or `null` years as a quick health probe.
- **A partial corpus refresh is acceptable.** Files that fail to parse are logged and skipped. A refresh that goes from 56 to 53 indexed reports without operator intervention indicates three files have rotted or changed format; investigate before assuming the corpus is fully refreshed.
- **The tokeniser is the FTS5 built-in `porter unicode61`.** No custom dictionaries, no language detection, no synonym expansion. Reports in languages other than English will tokenise, but retrieval precision will degrade as the Porter stemmer and Unicode-61 case folding are tuned for English. Multilingual coverage is a known gap; the current corpus is English-only.
- **SIGHUP is cheap; restart is cheap.** Either resets the index. Prefer SIGHUP during normal operations to keep container logs and metric series continuous; prefer a full restart when also changing server configuration or after a container image upgrade.

---

## 🗂 Repository layout

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

## 🔧 Tools

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

## 🛰 Data path

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

## 🚀 Quickstart

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

## 🏛 Architecture choices

- SQL is built with parameter binding. Dataset identifiers and column names are whitelisted against the in-process `TABLE_SCHEMAS` map before any query is constructed; no string interpolation touches user input.
- The FTS5 index is in-memory and rebuilt on SIGHUP. A single SIGHUP to the process refreshes both DuckDB and the report index without dropping connections.
- The container runs with a read-only root filesystem. Writable state is confined to named tmpfs volumes for the `uv` cache.

## 🧪 Tests

The repository ships with manual verification scripts that exercise the bug fixes from the initial release: technology alias resolution, plural-safe dim table lookup, and natural-language question tokenisation. To run the existing verifiers:

```bash
docker exec sparkscout bash -c 'ls /tmp/qa_*.py /tmp/trace_*.py'
docker exec sparkscout bash -c 'uv run --with duckdb==1.1.3 python /tmp/qa_fix_k.py'
```

The `qa_fix_*.py` scripts cover the bug fixes shipped in the initial release: technology alias resolution, plural-safe dim table lookup, and natural-language question tokenisation.

## ⚠️ Known issues

- `sparkscout_search_reports` uses a phrase-quoted FTS5 query; multi-word natural-language questions work better through `sparkscout_answer_question`, which tokenises the question, drops stopwords, and OR-merges per-term BM25 hits.

## 📜 License

- SparkScout source code: see [LICENSE](./LICENSE). MIT with an appended clause covering intellectual property in upstream content.
- Retrieved data and report text: see [NOTICE](./NOTICE). The statistics and publication text returned by this server remain subject to the upstream publisher's terms of use.

## 🙏 Acknowledgement

This server is a thin interface over publicly available renewable energy data. All statistical findings carry inline citations; all publication excerpts carry the original citation block. Reuse of retrieved content should preserve those citations.
