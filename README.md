![License](https://img.shields.io/badge/license-MIT%20%2B%20IP%20carve--out-blue)
![Python](https://img.shields.io/badge/python-3.13%2B-blue)
![MCP](https://img.shields.io/badge/MCP-FastMCP%204.0-purple)
![Datasets](https://img.shields.io/badge/datasets-8-green)
![Observations](https://img.shields.io/badge/IRENA%20observations-196k-green)
![Status](https://img.shields.io/badge/status-pre--release-orange)

# SparkScout MCP

Renewable energy data for AI assistants, with the source attached.

> [!IMPORTANT]
> **Project status: pre-release, single-operator deployment.** The repository contains the source code and the public documentation; the live MCP endpoint is not yet open for general registration. The [Quickstart](#-quickstart) below brings up a working local instance in five commands. The [Status of the corpus](#-status-of-the-corpus) section further down sets out what the corpus covers today, what is not yet covered, and what to expect from the next refresh.
>
> The seven statistical datasets and the publication corpus are governed by the upstream publisher's terms of use; see [NOTICE](./NOTICE) for attribution and reuse rules.

## Contents

- [What it is](#-what-it-is)
- [Who it is for](#-who-it-is-for)
- [Quickstart](#-quickstart)
- [Worked example](#-worked-example)
- [Tools](#-tools)
- [Cost corpus](#-cost-corpus)
- [Status of the corpus](#-status-of-the-corpus)
- [Data path](#-data-path)
- [Architecture choices](#-architecture-choices)
- [Repository layout](#-repository-layout)
- [Tests](#-tests)
- [Known issues](#-known-issues)
- [License](#-license)
- [Acknowledgement](#-acknowledgement)

## 🛰️ What it is

SparkScout is an MCP server that exposes a curated renewable-energy corpus to AI assistants. Every response carries the citation needed to trace the figure or excerpt back to its source.

The corpus at this revision holds 56 IRENA publications and 8 statistical datasets (196,696 rows) covering power capacity, electricity generation, renewable share, heat generation, public finance flows, and weighted-average LCOE.

The server exposes 12 MCP tools. A natural-language question can be answered end to end: search the publication corpus, retrieve a chapter, surface the dataset that holds the quantitative answer, and return both with citations. The same tools also serve quick factual lookups against the statistical tables.

## 👥 Who it is for

- **Energy analysts and policy researchers** who need a number or finding with the citation attached. The answer comes back tagged with the dataset or publication it came from; the analyst verifies against the source.
- **Agent builders** who want to wire a renewable-energy corpus into Claude, Cursor, Cline, Continue, or any MCP-compatible client. The 12 tools are the contract; `docs/integrate.md` carries the per-client setup blocks.
- **Operators** who run their own instance. The corpus is read-only at runtime; a local DuckDB snapshot and a directory of Markdown reports are the only inputs.

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

## 💬 Worked example

A natural-language question, end to end. The user asks the assistant; the assistant calls SparkScout on the user's behalf; the answer comes back with the citation that makes it usable.

> **User:** What was Brazil's installed solar capacity in 2024?
>
> **Assistant (after calling `irena_query_dataset`):** Brazil's installed solar PV capacity at the end of 2024 was 53,107 MW, up from 37,557 MW at the end of 2023. Source: IRENA (2026), Renewable Capacity Statistics 2026.

The full call sequence, the filter surface, and the citation block are documented in `docs/integrate.md`.

## 🧰 Tools

| Tool | Layer | Purpose |
|---|---|---|
| `irena_list_reports` | reports | List publications in the corpus |
| `irena_get_report` | reports | Fetch a report body or single chapter |
| `irena_search_reports` | reports | Hybrid search across reports (BM25 + dense, fused via RRF) |
| `irena_embed_health` | diagnostics | Embedding-store health (operator-side; model, dim, indexed count) |
| `irena_cite` | reports | Formatted citation string |
| `irena_list_datasets` | datasets | List the 8 statistical datasets (7 PxWeb + 1 cost corpus) |
| `irena_get_dataset_meta` | datasets | Schema and sample codes for one dataset |
| `irena_query_dataset` | datasets | Filtered, parameterised query with citations |
| `irena_query_dataset_aggregations` | datasets | Group-by with sum, avg, count, min, max |
| `irena_get_dataset_value` | datasets | Convenience scalar lookup |
| `irena_sample_dataset` | datasets | Random sample rows |
| `irena_answer_question` | cross | Hybrid natural-language search, dataset hints, and per-retrieval transparency |

All 12 tools return JSON. Dataset responses include an inline citation block in the form `[data: <dataset_id>, rows=N, filter=...]`.

## 💰 Cost corpus

SparkScout exposes a curated extract of the IRENA *Renewable Power Generation Costs 2025* report alongside the IRENASTAT PxWeb datasets. The extract is loaded as a second, read-only DuckDB file attached under the schema name `cost`, so the same dataset tools can query it without a separate path.

| Dataset | Dimensions | Coverage |
|---|---|---|
| `lcoe_weighted` | region, technology, country, year | Weighted-average LCOE from the IRENA 2025 cost report |

Each metric is stored in its own table rather than collapsed into a single wide table, because units and scope conditions differ across the report (USD/MWh vs USD/kW vs %, country-level vs project-finance aggregates, weighted vs simple averages). Per-table storage preserves that fidelity.

> [!NOTE]
> The remaining extracts (installed cost, capacity factor, O&M, WACC, financing, price components) are loaded into the database but not yet surfaced through the dataset tools. They will be registered incrementally as the schema stabilises. Adding any one is a 10-line `TABLE_SCHEMAS` entry plus dim-table lookups for the columns it filters on.

## 📊 Status of the corpus

The numbers below are pulled live from the DuckDB snapshot at the time of this revision (2026-09-08). Run `irena_list_datasets` against the running server to refresh after pulling a new snapshot.

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
| `lcoe_weighted` | 382 | 2010-2024 | USD/MWh (2024 real) | region, technology, country, year |

### Publications

56 markdown reports indexed. Energy transition outlooks, technology briefings (solar, wind, hydrogen, storage), regional analyses, policy briefs. Year, ISBN, and citation are extracted from each report's frontmatter.

### Covered today

> [!NOTE]
> **Covered:** installed power generation capacity and electricity generation by country and technology; renewable share of capacity and generation; heat generation by country and technology; public financial flows for renewable energy by recipient country and technology; weighted-average LCOE by technology, region, country, and year (IRENA Renewable Power Generation Costs 2025 corpus); full-text search across the indexed publication corpus, with chapter-level retrieval and citation.

### Not covered yet

> [!CAUTION]
> **Not yet covered:**
> - **Project-level data.** The current datasets are aggregate country and region views. Individual power plants, project pipelines, and financial deals are out of scope.
> - **Sub-annual granularity.** All datasets report on an annual basis. Quarterly and monthly series are not in scope.
> - **Non-energy mitigation topics.** Land use, water use, and emissions factors live outside the energy statistics series.
> - **Live network access.** The MCP endpoint is not yet registered publicly. The [Quickstart](#-quickstart) runs the server locally.
> - **Cost corpus tables beyond `lcoe_weighted`.** TIC, CF, O&M, WACC, financing, price, and cost components exist in the `cost` DuckDB schema but are not yet registered in `TABLE_SCHEMAS`, so the dataset tools cannot reach them.

## 🗺️ Data path

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
              │  12 tools, SIGHUP-reload│
              └──┬──────────────────┬──┘
                 │                  │
       DuckDB ◄──┘                  └──► SQLite FTS5 (in-memory)
       /data/irena/irena.duckdb       /data/reports/*.md
       (read-only)                   (rebuilt on SIGHUP)
```

Two storage backends, both read-only at runtime. DuckDB serves the 7 statistical tables; the FTS5 index is rebuilt from the markdown folder on startup or on SIGHUP. The operator guide (`docs/operator-guide.md`) covers the full ingestion pipeline, the chunking strategy, and the refresh lifecycle in detail.

## 🌐 Architecture choices

- SQL is built with parameter binding. Dataset identifiers and column names are whitelisted against the in-process `TABLE_SCHEMAS` map before any query is constructed; no string interpolation touches user input.
- The FTS5 index is in-memory and rebuilt on SIGHUP. A single SIGHUP to the process refreshes both DuckDB and the report index without dropping connections.
- The DuckDB file is opened `read_only=True`. A concurrent refresh that swaps the file via `os.replace` is safe; the running server holds an open file descriptor to the old inode until its next query, which then transparently opens the new file.
- The container runs with a read-only root filesystem. Writable state is confined to named tmpfs volumes for the `uv` cache.
- All MCP tool handlers are `async`; blocking DuckDB and FTS5 I/O is wrapped in `asyncio.to_thread` so the FastMCP event loop multiplexes concurrent sessions. Verified at 10 concurrent users with 0 malformed responses.
- `irena_search_reports` and `irena_answer_question` do hybrid retrieval: BM25 over the in-memory FTS5 index plus dense cosine similarity over `nomic-embed-text` 768-dim vectors, fused via Reciprocal Rank Fusion (k=60). The dense vectors live in a separate DuckDB file (`IRENA_DATA_DIR/embeddings.duckdb`), pre-computed on the host and bind-mounted read-only into the container. Each hit carries per-retriever ranks and scores plus a `sources` list.

## 🗂 Repository layout

```
sparkscout/
├── app/
│   ├── Dockerfile             Python 3.13-slim, runs under uv
│   ├── fastmcp.json           FastMCP runtime config
│   ├── server.py              Entry point, table schemas, SIGHUP reload
│   ├── stress_harness.py      Concurrent-session verifier (app/stress_harness.py)
│   └── tools/
│       ├── datasets.py        6 dataset tools over DuckDB
│       ├── duckdb_loader.py   Read-only DuckDB connection manager
│       ├── embeddings.py      nomic-embed-text client + vector store
│       ├── fts5_index.py      In-memory SQLite FTS5 report index
│       ├── fusion.py          irena_answer_question (hybrid retrieval)
│       └── reports.py         4 report tools + irena_embed_health
├── docker-compose.yml         Local stack
├── docs/
│   └── integrate.md           Per-client MCP setup blocks
├── LICENSE                    MIT plus IP carve-out
├── NOTICE                     Third-party data attribution
└── .gitignore                 Excludes operator-only paths
```

## ✅ Tests

The repository ships with a stress harness at `app/stress_harness.py` and manual verification scripts that exercise the bug fixes from the initial release: technology alias resolution, plural-safe dim table lookup, and natural-language question tokenisation.

```bash
# Stress harness: run 100 calls at --users 5 against a local or remote endpoint
python app/stress_harness.py --users 5 --calls 100

# Inside the container:
docker exec sparkscout bash -c 'ls /tmp/qa_*.py /tmp/trace_*.py'
docker exec sparkscout bash -c 'uv run --with duckdb==1.1.3 python /tmp/qa_fix_k.py'
```

The pre-ship gate is 0 malformed responses and 0 silent filter coercions across the run.

To rebuild the embedding store after adding reports or switching models:

```bash
# Run on the host where mg-ollama is reachable. Writes
# IRENA_DATA_DIR/embeddings.duckdb; bind-mounted into the container.
uv run --with duckdb python tools/embed_corpus.py --reindex
```

## ⚠️ Known issues

- When a natural-language question has no BM25 keyword matches, hybrid retrieval falls back to the dense retriever and returns hits flagged with `sources: ["dense"]` along with a `notes` line in `irena_answer_question`. This is intentional transparency for LLM agents, not a bug. Verify dense-only hits against the cited publication before quoting.

## 📄 License

- SparkScout source code: see [LICENSE](./LICENSE). MIT with an appended clause covering intellectual property in upstream content.
- Retrieved data and report text: see [NOTICE](./NOTICE). The statistics and publication text returned by this server remain subject to the upstream publisher's terms of use.

## 🙏 Acknowledgement

This server is a thin interface over publicly available renewable energy data. All statistical findings carry inline citations; all publication excerpts carry the original citation block. Reuse of retrieved content should preserve those citations.
