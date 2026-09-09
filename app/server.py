"""SparkScout — IRENA reports + datasets MCP server."""

import json
import logging
import os
import signal
from datetime import datetime, timezone

from fastmcp import FastMCP
from fastmcp.server.auth import StaticTokenVerifier
from starlette.requests import Request
from starlette.responses import PlainTextResponse, JSONResponse

from tools.duckdb_loader import DuckDBLoader
from tools.fts5_index import FTS5Index
from tools import reports as reports_tools
from tools import datasets as datasets_tools
from tools import fusion as fusion_tools

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sparkscout")

IRENA_REPORTS_DIR = os.environ.get("IRENA_REPORTS_DIR", "/data/reports")
IRENA_DATA_DIR = os.environ.get("IRENA_DATA_DIR", "/data/irena")
DUCKDB_PATH = os.environ.get("DUCKDB_PATH", os.path.join(IRENA_DATA_DIR, "irena.duckdb"))
BEARER_TOKEN = os.environ.get("FASTMCP_BEARER", "")

# SSoT for table schemas — used by both the dataset tools and the
# dataset meta tool. Adding a new IRENA source = adding one entry here.
TABLE_SCHEMAS = {
    "country_capacity": {
        "title": "Electricity capacity statistics by country/area, technology, grid connection, and year",
        "measure_column": "Electricity capacity statistics",
        "units": "MW",
        "dimension_columns": ["Country/area", "Technology", "Grid connection", "Year"],
        "filter_aliases": {
            "Country/area": "countries",
            "Technology": "technologies",
            "Grid connection": "grid_connection",
            "Year": "years",
        },
    },
    "country_generation": {
        "title": "Electricity generation statistics by country/area, technology, data type, grid connection, and year",
        "measure_column": "Electricity generation statistics",
        "units": "GWh",
        "dimension_columns": ["Country/area", "Technology", "Data Type", "Grid connection", "Year"],
        "filter_aliases": {
            "Country/area": "countries",
            "Technology": "technologies",
            "Data Type": "data_type",
            "Grid connection": "grid_connection",
            "Year": "years",
        },
    },
    "region_capacity": {
        "title": "Electricity capacity statistics by region, technology, grid connection, and year",
        "measure_column": "Electricity capacity statistics",
        "units": "MW",
        "dimension_columns": ["Region", "Technology", "Grid connection", "Year"],
        "filter_aliases": {
            "Region": "regions",
            "Technology": "technologies",
            "Grid connection": "grid_connection",
            "Year": "years",
        },
    },
    "region_generation": {
        "title": "Electricity generation statistics by region, technology, data type, and year",
        "measure_column": "Electricity generation statistics",
        "units": "GWh",
        "dimension_columns": ["Region", "Technology", "Data Type", "Year"],
        "filter_aliases": {
            "Region": "regions",
            "Technology": "technologies",
            "Data Type": "data_type",
            "Year": "years",
        },
    },
    "re_share": {
        "title": "Renewable energy share of electricity capacity and generation (%) by region/country/area, indicator, and year",
        "measure_column": "Renewable energy share of electricity capacity and generation (%)",
        "units": "%",
        "dimension_columns": ["Region/country/area", "Indicator", "Year"],
        "filter_aliases": {
            "Region/country/area": "regions",
            "Indicator": "indicators",
            "Year": "years",
        },
    },
    "heat_generation": {
        "title": "Heat generation (TJ) by country/area, technology, grid connection, and year",
        "measure_column": "Heat generation (TJ)",
        "units": "TJ",
        "dimension_columns": ["Country/area", "Technology", "Grid connection", "Year"],
        "filter_aliases": {
            "Country/area": "countries",
            "Technology": "technologies",
            "Grid connection": "grid_connection",
            "Year": "years",
        },
    },
    "lcoe_weighted": {
        "title": "IRENA Renewable Power Generation Costs 2025 — weighted-average LCOE by technology, region, country, and year",
        "schema_name": "cost",
        "measure_column": "value",
        "units": "USD/MWh (2024 real)",
        "dimension_columns": ["region", "technology_id", "country", "year"],
        "filter_aliases": {
            "region": "regions",
            "technology_id": "technologies",
            "country": "countries",
            "year": "years",
        },
    },
    "public_investments": {
        "title": "Public Investments (2022 Million USD) by country/area, technology, and year",
        "measure_column": "Public Investments (2022 Million USD)",
        "units": "Million USD (2022 prices)",
        "dimension_columns": ["Country/area", "Technology", "Year"],
        "filter_aliases": {
            "Country/area": "countries",
            "Technology": "technologies",
            "Year": "years",
        },
    },
}


# Init state
cost_path = os.environ.get("COST_DUCKDB_PATH", os.path.join(IRENA_DATA_DIR, "irena_cost.duckdb"))
duckdb_loader = DuckDBLoader(DUCKDB_PATH, cost_path=cost_path)
fts5_index = FTS5Index(IRENA_REPORTS_DIR)

try:
    duckdb_loader.open()
    log.info(f"opened DuckDB read-only: {DUCKDB_PATH}")
except Exception as e:
    log.error(f"failed to open DuckDB: {e}")
    raise

try:
    fts5_index.build()
    log.info(f"built FTS5 index from {IRENA_REPORTS_DIR}")
except Exception as e:
    log.error(f"failed to build FTS5 index: {e}")
    raise


# FastMCP app — token-gated at every tool call
auth = StaticTokenVerifier(tokens={BEARER_TOKEN: {"client_id": "sparkscout"}}) if BEARER_TOKEN else None
mcp = FastMCP("SparkScout", auth=auth, instructions="IRENA reports + datasets MCP. Tools are namespaced sparkscout_*.")


# Health endpoint (FastMCP mounts this when transport is HTTP)
@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    state = {
        "service": "sparkscout",
        "duckdb": "ok" if duckdb_loader.con is not None else "down",
        "fts5_documents": fts5_index.doc_count(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(state)


# Register tool groups
reports_tools.register(mcp, IRENA_REPORTS_DIR, fts5_index)
datasets_tools.register(mcp, duckdb_loader, TABLE_SCHEMAS)
fusion_tools.register(mcp, fts5_index, TABLE_SCHEMAS)


# SIGHUP handler — re-open DuckDB handle and rebuild FTS5 without restart
def _reload(_signum, _frame):
    log.info("SIGHUP received, reloading DuckDB + FTS5")
    try:
        duckdb_loader.reload()
        log.info("DuckDB reloaded")
    except Exception as e:
        log.error(f"DuckDB reload failed: {e}")
    try:
        fts5_index.build()
        log.info(f"FTS5 rebuilt: {fts5_index.doc_count()} docs")
    except Exception as e:
        log.error(f"FTS5 rebuild failed: {e}")


if __name__ == "__main__":
    # Register SIGHUP handler BEFORE entering the FastMCP event loop.
    signal.signal(signal.SIGHUP, _reload)
    log.info("starting FastMCP HTTP transport on :8000")
    mcp.run(transport="http", host="0.0.0.0", port=8000)
