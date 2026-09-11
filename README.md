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

SparkScout is an MCP server that gives an AI assistant a large, citable body of renewable-energy knowledge to draw on. Every response carries the citation needed to trace the figure or excerpt back to its source, so the assistant's answer is verifiable end to end.

A natural-language question can be answered in a single round trip: the server searches the publication corpus, retrieves the relevant chapter, surfaces the dataset that holds the quantitative answer, and returns both with citations. The same tools also serve quick factual lookups against the statistical tables.

The corpus grows by ingesting new publishers and new publications; the [📊 Status of the corpus](#-status-of-the-corpus) section below carries the current numbers and the per-dataset detail.

## 👥 Who it is for

- **Decision-makers** who need a numeric answer with the citation attached. The answer comes back tagged with the dataset or publication it came from; the reader verifies against the source before quoting.
- **Agent builders** who want to wire a renewable-energy corpus into Claude, Cursor, Cline, Continue, or any MCP-compatible client. The 12 MCP tools are the contract; see [🧪 Integration guide](./docs/integrate.md) for per-client setup blocks.
- **Operators** who run their own instance. The corpus is read-only at runtime; a local DuckDB snapshot and a directory of source documents are the only inputs.

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

Three live tool calls from the running server. The user asks the assistant; the assistant calls SparkScout on the user's behalf; the response carries the citation needed to verify every figure or excerpt.

### Example 1: a precise question with a known dataset

> **User:** What was Brazil's installed solar capacity in 2024?
>
> **Assistant** calls `irena_query_dataset(dataset_id="country_capacity", filters={"countries": ["Brazil"], "technologies": ["Solar photovoltaic"], "years": ["2024"]}, limit=5)`. The tool translates the friendly labels to dim codes (Brazil → BRA, Solar photovoltaic → tech 2, 2024 → 24), runs the parameter-bound query, and returns:
>
> ```json
> {
>   "dataset_id": "country_capacity",
>   "columns": ["Country/area", "Technology", "Grid connection", "Year", "Electricity capacity statistics"],
>   "rows": [
>     {"Country/area": "BRA", "Technology": "2", "Grid connection": "0", "Year": "24", "Electricity capacity statistics": 53107.46},
>     {"Country/area": "BRA", "Technology": "2", "Grid connection": "1", "Year": "24", "Electricity capacity statistics": 6.66}
>   ],
>   "row_count": 2,
>   "citations": ["[data: country_capacity, rows=2, filter={"countries": ["Brazil"], "technologies": ["Solar photovoltaic"], "years": ["2024"]}]"],
>   "filters_applied": {"countries": ["BRA"], "technologies": ["2"], "years": ["24"]},
>   "filters_dropped": {},
>   "sql_executed": "SELECT ... FROM "country_capacity" WHERE "Country/area" IN (?) AND "Technology" IN (?) AND "Year" IN (?) LIMIT 5"
> }
> ```
>
> Brazil's installed solar PV capacity at the end of 2024 was **53,107 MW**. The citation block identifies the dataset; the response includes the SQL that ran, the dim codes that matched, and the drop list (empty here) so the assistant knows nothing was silently coerced.

### Example 2: a precise question with the cost corpus

The same tool serves the curated extract of the cost report. Same call shape, different `dataset_id`:

> **User:** What was the weighted-average LCOE for solar PV in the World region in 2025?
>
> **Assistant** calls `irena_query_dataset(dataset_id="lcoe_weighted", filters={"regions": ["World"], "technologies": ["solar_pv"], "years": ["2025"]}, limit=3)`. The cost corpus lives in a second DuckDB attached as schema `cost`, so the SQL targets `cost.fact_lcoe_weighted`:
>
> ```json
> {
>   "dataset_id": "lcoe_weighted",
>   "title": "Levelised cost of electricity (LCOE), weighted average, by technology, region, country, and year",
>   "columns": ["technology_id", "region", "country", "year", "value"],
>   "rows": [
>     {"technology_id": "solar_pv", "region": "World", "country": "NN", "year": 2025, "value": 44.0},
>     {"technology_id": "solar_pv", "region": "World", "country": "NN", "year": 2025, "value": 55.0}
>   ],
>   "row_count": 2,
>   "citations": ["[data: lcoe_weighted, rows=2, filter={"regions": ["World"], "technologies": ["solar_pv"], "years": ["2025"]}]"],
>   "filters_applied": {"regions": ["World"], "technologies": ["solar_pv"], "years": ["2025"]},
>   "filters_dropped": {},
>   "sql_executed": "SELECT ... FROM "cost"."fact_lcoe_weighted" WHERE "region" IN (?) AND "technology_id" IN (?) AND "year" IN (?) LIMIT 3"
> }
> ```
>
> Two rows: solar PV weighted-average LCOE in the World region in 2025 was **44 USD/MWh** (cross-tech aggregate, including and excluding China) and **55 USD/MWh** (a different scope condition from the same Fig 1.2 source). The assistant cites both with the source metric label in `context`, and notes the scope distinction before quoting either figure.

### Example 3: a paraphrased question with hybrid retrieval

When the question is paraphrased the way a policy researcher actually asks it, the dataset tool cannot resolve it on its own. The assistant switches to the cross-tool:

> **User:** What is the role of battery storage in West Africa mini-grids?
>
> **Assistant** calls `irena_answer_question(question="What is the role of battery storage in West Africa mini-grids?", top_k_reports=3)`. The hybrid retriever fuses BM25 over the publication corpus with dense cosine similarity over `nomic-embed-text` 768-dim vectors:
>
> ```json
> {
>   "question": "What is the role of battery storage in West Africa mini-grids?",
>   "reports": [
>     {
>       "report_id": "IRENA_TEC_Battery_storage_minigrids_W_Africa_2026",
>       "excerpt": "While global efforts are directed towards tripling renewable power capacity by 2030 under the COP 28 UAE Consensus, in support of the Paris Agreement's 1.5°C climate goal, many regions continue to face significant challenges in providing decent and affordable electricity access to all. Western Africa is the second-largest…",
>       "rrf_score": 0.0164,
>       "sources": ["dense"]
>     },
>     {
>       "report_id": "IRENA_TEC_Powering_climate_resilience_FWA_2026",
>       "excerpt": "Francophone West Africa (FWA) – comprising Benin, Burkina Faso, Côte d'Ivoire, Guinea, Mali, Niger, Senegal and Togo – faces a convergence of intensifying climate risks and persistent gaps in electricity access and service quality. Climate hazards in the region are already evident. Temperatures across the Sahel…",
>       "rrf_score": 0.0159,
>       "sources": ["dense"]
>     },
>     {
>       "report_id": "IRENA_INN_Sustainable_development_renewables_Senegal_2026",
>       "excerpt": "Senegal is a coastal state located at the westernmost tip of Africa, serving as a bridge between the Sahel and the tropical savannah. With a population of 19 million in 2025 and a rapidly growing economy – its GDP has tripled over the past two decades – the country is among Africa's fastest-growing economies…",
>       "rrf_score": 0.0156,
>       "sources": ["dense"]
>     }
>   ],
>   "citation_block": "[reports: IRENA_TEC_Battery_storage_minigrids_W_Africa_2026, IRENA_TEC_Powering_climate_resilience_FWA_2026, IRENA_INN_Sustainable_development_renewables_Senegal_2026]",
>   "notes": [
>     "BM25 returned no hits; results are dense-only and may need verification"
>   ],
>   "retrieval": {"bm25_only": false, "dense_only": true, "bm25_count": 0, "dense_count": 12}
> }
> ```
>
> Three reports cover the question, all from the West Africa / Sahel region. The lead excerpt on each hit is real content from the body, not frontmatter boilerplate or a table-of-contents entry. The `retrieval` block flags the answer as **dense-only** (BM25 returned zero hits, so the retriever leaned entirely on semantic similarity), and the assistant notes that the user should verify against the cited publications before quoting. Hit-shape carries `rrf_score`, per-retriever `sources`, the `report_id` for the next-step citation lookup, and an `excerpt` field that holds the **first paragraph of the body**, capped at 320 chars. The excerpt is a fallback snippet, not the answer to the question; the assistant follows up with `irena_get_report(report_id=…, chapter=…)` to read the chapter that actually discusses the topic.

The full call sequence, the filter surface, and the citation block format are documented in the [🧪 Integration guide](./docs/integrate.md).

## 🧰 Tools

| Tool | Layer | Purpose |
|---|---|---|
| `irena_list_reports` | reports | List publications in the corpus |
| `irena_get_report` | reports | Fetch a report body or single chapter |
| `irena_search_reports` | reports | Hybrid search across reports (BM25 + dense, fused via RRF) |
| `irena_embed_health` | diagnostics | Embedding-store health (operator-side; model, dim, indexed count) |
| `irena_cite` | reports | Formatted citation string |
| `irena_list_datasets` | datasets | List the registered statistical datasets |
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

The corpus is a working catalogue. It grows by ingesting new publishers, refreshing existing ones on the upstream publication cycle, and registering new dataset shapes as the schema stabilises. The numbers below reflect the snapshot at the time of this README revision; run `irena_list_datasets` against the running server for the live count.

The current revision of the corpus draws on a single upstream publisher of public renewable-energy statistics and the publication archive that publisher curates. Attribution and reuse rules are documented in [NOTICE](./NOTICE). New publishers are added without breaking existing tool contracts; the framework treats every publisher the same way.

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

A growing corpus of markdown reports spanning energy transition outlooks, technology briefings (solar, wind, hydrogen, storage), regional analyses, and policy briefs. Run [`irena_list_reports`](./docs/integrate.md) to enumerate the publications currently indexed; the live count and per-report metadata are returned in the response. Year, ISBN, and the original citation block are extracted from each report's frontmatter so the agent can cite without re-fetching.

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
│   ├── stress_harness.py      Concurrent-session verifier
│   └── tools/
│       ├── datasets.py        6 dataset tools over DuckDB
│       ├── duckdb_loader.py   Read-only DuckDB connection manager
│       ├── embeddings.py      nomic-embed-text client + vector store
│       ├── fts5_index.py      In-memory SQLite FTS5 report index
│       ├── fusion.py          irena_answer_question (hybrid retrieval)
│       └── reports.py         5 report tools + irena_embed_health
├── docker-compose.yml         Local stack
├── docs/
│   └── integrate.md           Per-client MCP setup blocks
├── LICENSE                    MIT plus IP carve-out
├── NOTICE                     Third-party data attribution
└── .gitignore                 Excludes operator-only paths
```

## ✅ Tests

The repository ships with a stress harness at `app/stress_harness.py` that exercises the full tool surface under concurrent load, plus one targeted trace script (`app/trace_k2.py`) for silent-filter-coerce regression work.

```bash
# Stress harness against the local container (10 batches × 100 calls, 5 concurrent users)
python app/stress_harness.py \
  --host <proxmox-host> --lxc <lxc-id> \
  --url http://127.0.0.1:7100/mcp \
  --token "$FASTMCP_BEARER" \
  --batches 10 --per-batch 100 --users 5
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
- The corpus currently reflects a single upstream publisher's publication cycle. Multi-publisher coverage (additional public sources, climate-policy documents) is in active planning and will be added without breaking the existing tool contracts.
- `irena_query_dataset` and the aggregations tool surface any filter value that cannot resolve to a dimension code under `filters_dropped`. Each entry carries the original `value` and a `reason` string (`null value`, `integer scalar; not a dim code`, `boolean scalar; not a dim code`, `non-integer float; not a dim code`, `empty string`). LLMs that send placeholder scalars (for example `0`, `True`, `None`) should read this block before assuming a query returned no rows because of a real empty result.

## 📄 License

- SparkScout source code: [LICENSE](./LICENSE). MIT with an appended clause covering intellectual property in upstream content.
- Retrieved data and report text: [NOTICE](./NOTICE). The statistics and publication text returned by this server remain subject to the upstream publisher's terms of use.

## 🙏 Acknowledgement

This server is a thin interface over publicly available renewable energy data. All statistical findings carry inline citations; all publication excerpts carry the original citation block. Reuse of retrieved content should preserve those citations.
