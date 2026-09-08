# SparkScout MCP

A Model Context Protocol server that gives AI assistants and agents access to IRENA renewable energy data and publications.

Two sources, one interface. The server exposes 11 tools over IRENA's structured statistics (DuckDB) and a corpus of IRENA reports (SQLite FTS5). Every response carries the citation needed to attribute findings back to the source dataset or publication.

![License](https://img.shields.io/badge/license-MIT%20%2B%20IRENA%20IP-blue)
![Python](https://img.shields.io/badge/python-3.13%2B-blue)
![MCP](https://img.shields.io/badge/MCP-FastMCP%204.0-purple)
![Coverage](https://img.shields.io/badge/IRENA%20observations-196k-green)

## What it does

An AI client connected to SparkScout can:

- Search IRENA publications by natural-language question, retrieve chapter-level excerpts, and produce formatted citations.
- Query IRENA statistical datasets with structured filters, run grouped aggregations, sample rows, and retrieve scalar values.
- Combine the two: take a question, find the most relevant reports, and surface the datasets that hold the quantitative answer.

The corpus at this revision holds 56 IRENA publications and 7 statistical datasets (196,314 rows) covering power capacity, electricity generation, renewable energy shares, heat generation, and public finance flows.

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
├── LICENSE                    MIT plus IRENA IP carve-out
├── NOTICE                     Third-party data attribution
└── .gitignore                 Excludes operator-only paths
```

## Tools

| Tool | Layer | Purpose |
|---|---|---|
| `sparkscout_list_reports` | reports | List IRENA publications in the corpus |
| `sparkscout_get_report` | reports | Fetch a report body or single chapter |
| `sparkscout_search_reports` | reports | BM25 full-text search across reports |
| `sparkscout_cite` | reports | Formatted citation string |
| `sparkscout_list_datasets` | datasets | List the 7 IRENA statistical datasets |
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

Prerequisites: Python 3.13+, [uv](https://docs.astral.sh/uv/), DuckDB 1.1.3, FastMCP 4.0.0, the IRENA DuckDB snapshot at `./data/irena/irena.duckdb`, and IRENA report markdowns at `./data/reports/`.

Clone, point at data, run:

```bash
git clone https://github.com/ElectrifySimon/sparkscout
cd sparkscout

# Place the IRENA DuckDB snapshot and the report markdown folder
mkdir -p data/irena data/reports
# cp /path/to/irena.duckdb data/irena/
# cp /path/to/reports/*.md data/reports/

# Optional: set the bearer token to enable the auth verifier
export FASTMCP_BEARER=<your-token>

# Start the server (resolves deps via uv on first run)
uv run --with fastmcp==4.0.0 --with duckdb==1.1.3 python app/server.py
```

The server binds to `0.0.0.0:8000`. Probe health:

```bash
curl http://127.0.0.1:8000/health
# {"service":"sparkscout","duckdb":"ok","fts5_documents":56,"timestamp":"..."}
```

To register with an MCP client, point the client at the running endpoint and pass the bearer token. The MCP client config is not yet published: deployment information will be added when public access is opened.

## Datasets

Live coverage pulled from DuckDB on this revision:

| Dataset | Rows | Years | Units | Dimensions |
|---|---|---|---|---|
| `country_capacity` | 73,432 | 2000-2025 | MW | country, technology, grid connection, year |
| `country_generation` | 87,256 | 2000-2024 | GWh | country, technology, data type, grid connection, year |
| `region_capacity` | 4,399 | 2000-2025 | MW | region, technology, grid connection, year |
| `region_generation` | 2,615 | 2000-2024 | GWh | region, technology, data type, year |
| `re_share` | 10,826 | 2000-2025 | percent | region/country, indicator, year |
| `heat_generation` | 9,708 | 2000-2024 | TJ | country, technology, grid connection, year |
| `public_investments` | 8,078 | 2000-2024 | Million USD (2022 prices) | country, technology, year |

To refresh these counts after pulling new IRENA data, run `sparkscout_list_datasets` against the live server. Filter labels are resolved against the dimension tables: `countries`, `technologies`, `years`, `regions`, `indicators`, `data_type`, `grid_connection`. Common aliases such as `Solar PV`, `Wind`, `Hydro` resolve to the same PxWeb codes an analyst would type.

## Architecture choices

- SQL is built with parameter binding. Dataset identifiers and column names are whitelisted against the in-process `TABLE_SCHEMAS` map before any query is constructed; no string interpolation touches user input.
- The FTS5 index is in-memory and rebuilt on SIGHUP. A single SIGHUP to the process refreshes both DuckDB and the report index without dropping connections.
- The container runs with a read-only root filesystem. Writable state is confined to named tmpfs volumes for the `uv` cache.

## Tests

The repository ships with manual verification scripts under `references/sparkscout-debug-recipes-2026-09-07.md`. Automated tests are not yet wired. To run the existing verifiers:

```bash
# Pull the QA scripts from the live container
docker exec sparkscout bash -c 'ls /tmp/qa_*.py /tmp/trace_*.py'
# Run a known-good reproducer end to end
docker exec sparkscout bash -c 'uv run --with duckdb==1.1.3 python /tmp/qa_fix_k.py'
```

The `qa_fix_*.py` scripts cover the bug fixes shipped in the initial release: technology alias resolution, plural-safe dim table lookup, and natural-language question tokenisation.

## Known issues

- `sparkscout_search_reports` uses a phrase-quoted FTS5 query; multi-word natural-language questions work better through `sparkscout_answer_question`, which tokenises the question, drops stopwords, and OR-merges per-term BM25 hits.
- The container-level Docker healthcheck has been reporting `unhealthy` for an extended period while the application `/health` endpoint returns 200. The two are unrelated; inspect with `docker inspect sparkscout` before treating container health as authoritative.

## License

- SparkScout source code: see [LICENSE](./LICENSE). MIT with an appended clause covering intellectual property in IRENA-sourced content.
- Retrieved IRENA content: see [NOTICE](./NOTICE). The statistics and publication text returned by this server remain subject to IRENA's own terms of use.

## Acknowledgement

This server is a thin interface over publicly available IRENA data. All statistical findings carry inline citations; all publications carry IRENA's own citation block. Reuse of retrieved content should preserve those citations.
