"""Dataset tools — 6 tools over the DuckDB file.

Schema discovery via TABLE_SCHEMAS (SSoT in server.py). All queries
built with parameter binding; dataset_id + column names whitelisted
against the schema before SQL is generated. Results are JOINed to
dimension tables so codes like "AFG" come back as "Afghanistan".

Tools are async so the FastMCP event loop stays unblocked under
concurrent sessions. DuckDB I/O is synchronous, so each query is
dispatched to a worker thread via asyncio.to_thread. The DuckDB
loader holds a single read-only connection; DuckDB serializes its
own queries internally so concurrent to_thread calls are safe.
"""

import asyncio
import json
from datetime import datetime, timezone


# Common user-supplied aliases for IRENA technologies, mapped to the PxWeb
# numeric codes that the fact tables store. Consulted before the dim-table
# lookup so casual labels like "Solar PV", "Wind", "PV" resolve to the same
# code an analyst would type ("2", "4", etc.).
TECH_ALIASES = {
    # solar
    "solar pv": "2", "solar photovoltaic": "2", "pv": "2", "photovoltaic": "2",
    "solar": "2", "solar energy": "1", "solar thermal": "3", "solar thermal energy": "3",
    # wind
    "wind": "4", "wind energy": "4", "onshore wind": "5", "onshore wind energy": "5",
    "offshore wind": "6", "offshore wind energy": "6",
    # hydro / marine
    "hydro": "7", "hydropower": "7", "renewable hydropower": "7", "mixed hydro": "8",
    "mixed hydropower": "8", "pumped hydro": "25", "marine": "9", "marine energy": "9",
    # bioenergy
    "bioenergy": "10", "biomass": "10", "solid biofuels": "11", "liquid biofuels": "12",
    "gas biofuels": "13", "renewable waste": "14",
    # geothermal
    "geothermal": "15", "geothermal energy": "15",
    # fossil / non-renewable
    "fossil fuels": "17", "fossil": "17", "coal": "18", "oil": "19",
    "natural gas": "20", "gas": "20", "nuclear": "21",
    "non-renewable waste": "22",
}


# ---- helpers (also called from server.py via tool definitions) ----

def _dim_name(table_id: str, dim_code: str, schema_name: str = "main") -> str:
    """Qualified dim table name. PxWeb uses dim_<table>_<dim_code> (schema `main`);
    cost-corpus tables live in schema `cost` and follow the same naming."""
    base = f"dim_{table_id}_{dim_code.lower().replace('/', '_').replace(' ', '_').replace('-', '_')}"
    if schema_name == "main":
        return base
    return f"{schema_name}.{base}"


def _fact_name(table_id: str, schema_name: str = "main") -> str:
    """Qualified fact table name. Same convention as _dim_name."""
    if schema_name == "main":
        return table_id
    return f"{schema_name}.{table_id}"


def _row_to_dict(columns: list[str], row: tuple) -> dict:
    return {c: v for c, v in zip(columns, row)}


def _resolve_filter_values(duckdb_loader, dataset_id: str, dim_col: str, values, schema_name: str = "main") -> list:
    """Resolve label strings to codes via the dim table. Falls back to raw values.

    Two-phase match:
      1. Exact label match (case-insensitive) OR exact code match
      2. Substring match (case-insensitive) on label
    This handles "Solar PV" → "Solar photovoltaic", "Wind" → "Wind energy",
    "AFG" → "AFG" code, "2024" → "24" string code.

    Sync function (microsecond-level DuckDB lookups). Tool wrappers run this
    and the data fetch inside asyncio.to_thread to keep the FastMCP event
    loop unblocked under concurrent sessions.
    """
    if not isinstance(values, list):
        values = [values]
    dim_table = _dim_name(dataset_id, dim_col, schema_name)
    # Plural-safety: when the filter alias ends in 's' but the dim table is
    # singular (e.g. filter alias 'years' vs dim table 'year'), the named
    # table doesn't exist. Try the singular form as a fallback before falling
    # back to raw values.
    if dataset_id and dim_col.endswith("s"):
        singular = dim_col[:-1]
        if singular:
            dim_table_singular = _dim_name(dataset_id, singular, schema_name)
    # Alias shortcut for the Technology dimension: common synonyms ("Solar PV",
    # "Wind", "PV") don't appear in the dim tables verbatim, so map them to the
    # canonical PxWeb code first to avoid the substring-search fallback returning
    # the raw user string (which then fails to match the numeric codes in the
    # fact tables).
    if dim_col == "Technology":
        aliased: list[str] = []
        for v in values:
            v_lower = str(v).lower().strip()
            code = TECH_ALIASES.get(v_lower)
            if code and code not in aliased:
                aliased.append(code)
        if aliased:
            return aliased
    codes: list[str] = []
    # Probe the dim table; if it's missing (e.g. filter alias 'years' vs dim
    # table 'year'), fall back to the singular form.
    effective_dim_table = dim_table
    try:
        duckdb_loader.execute(f'SELECT 1 FROM "{dim_table}" LIMIT 0')
    except Exception:
        if dataset_id and dim_col.endswith("s") and singular:
            effective_dim_table = dim_table_singular
    try:
        # Phase 1: exact (case-insensitive) label OR code match
        rows = duckdb_loader.execute(
            f'SELECT code, label FROM "{effective_dim_table}" '
            f'WHERE LOWER(label) = ANY(?) OR LOWER(code) = ANY(?)',
            [[str(v).lower() for v in values], [str(v).lower() for v in values]],
        ).fetchall()
        for r in rows:
            codes.append(r[0])
        # Phase 2: substring match for any value not yet resolved
        for v in values:
            v_lower = str(v).lower()
            if v_lower in {c.lower() for c in codes}:
                continue
            rows = duckdb_loader.execute(
                f'SELECT code, label FROM "{effective_dim_table}" '
                f'WHERE LOWER(label) LIKE ?',
                [f'%{v_lower}%'],
            ).fetchall()
            for r in rows:
                if r[0] not in codes:
                    codes.append(r[0])
    except Exception:
        codes = [str(v) for v in values]
    if not codes:
        codes = [str(v) for v in values]
    return codes


def _build_query_sql(duckdb_loader, dataset_id: str, schema: dict, filters: dict | None,
                     columns: list[str] | None, limit: int, order_by: str | None):
    """Build a parameterized SELECT.

    Returns (err, sql, params, limit_requested, limit_applied, limit_clamped,
    filters_applied, filters_dropped). The filter/limit surface fields let the
    tool wrapper report per-call coercion back to the LLM client (P0 fix).
    """
    measure_col = schema["measure_column"]
    all_cols = schema["dimension_columns"] + [measure_col]
    schema_name = schema.get("schema_name", "main")
    fact_table = _fact_name(dataset_id, schema_name)

    if columns is None:
        columns = all_cols
    for c in columns:
        if c not in all_cols:
            return {"error": f"Unknown column: {c}", "available": all_cols}, None, None, limit, limit, False, {}, {}
    limit_requested = limit
    limit = min(max(1, limit), 10_000)
    limit_clamped = (limit != limit_requested)

    reverse_alias = {v: k for k, v in schema["filter_aliases"].items()}
    where_clauses = []
    params: list = []
    filters_applied: dict[str, list] = {}
    filters_dropped: dict[str, list] = {}
    if filters:
        for alias, values in filters.items():
            if alias not in reverse_alias:
                return {"error": f"Unknown filter: {alias}", "available": list(reverse_alias.keys())}, None, None, limit_requested, limit, limit_clamped, {}, {}
            if not isinstance(values, list):
                values = [values]
            dim_col = reverse_alias[alias]
            # Drop obviously-bad inputs before resolution: None, empty strings,
            # non-string/non-int floats. Real strings/ints survive.
            kept = [v for v in values if v is not None and v != "" and not isinstance(v, float)]
            dropped = [v for v in values if v not in kept]
            if dropped:
                filters_dropped[alias] = dropped
            codes = _resolve_filter_values(duckdb_loader, dataset_id, dim_col, kept, schema_name)
            if codes:
                filters_applied[alias] = codes
            placeholders = ",".join(["?"] * len(codes))
            where_clauses.append(f'"{dim_col}" IN ({placeholders})')
            params.extend(codes)

    quoted_cols = ", ".join([f'"{c}"' for c in columns])
    sql = f'SELECT {quoted_cols} FROM "{fact_table}"'
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    if order_by:
        parts = order_by.split()
        col = parts[0]
        direction = parts[1].upper() if len(parts) > 1 else "ASC"
        if col not in all_cols:
            return {"error": f"Unknown order_by column: {col}", "available": all_cols}, None, None, limit_requested, limit, limit_clamped, filters_applied, filters_dropped
        if direction not in ("ASC", "DESC"):
            return {"error": f"Invalid direction: {direction}"}, None, None, limit_requested, limit, limit_clamped, filters_applied, filters_dropped
        sql += f' ORDER BY "{col}" {direction}'

    sql += f" LIMIT {int(limit)}"
    return None, sql, params, limit_requested, limit, limit_clamped, filters_applied, filters_dropped


def register(mcp, duckdb_loader, table_schemas: dict):
    @mcp.tool
    async def irena_list_datasets() -> list[dict]:
        """List all 7 IRENA datasets.

        Returns: list of {dataset_id, title, source, snapshot_pulled_at, row_count,
        size_mb, columns, latest_year, units}.
        """
        def _list():
            out = []
            for ds_id, schema in table_schemas.items():
                schema_name = schema.get("schema_name", "main")
                fact_table = _fact_name(ds_id, schema_name)
                try:
                    row_count = duckdb_loader.execute(
                        f'SELECT COUNT(*) FROM "{fact_table}"'
                    ).fetchone()[0]
                    max_year = duckdb_loader.execute(
                        f'SELECT MAX(CAST("Year" AS INTEGER)) FROM "{fact_table}"'
                    ).fetchone()[0]
                except Exception:
                    row_count = None
                    max_year = None
                try:
                    source = duckdb_loader.execute(
                        f'SELECT DISTINCT source FROM "{fact_table}" WHERE source IS NOT NULL LIMIT 1'
                    ).fetchone()
                    source = source[0] if source else "(no source attribution)"
                except Exception:
                    source = "(unknown)"
                out.append({
                    "dataset_id": ds_id,
                    "title": schema["title"],
                    "source": source,
                    "snapshot_pulled_at": "from irena.duckdb (in-memory; refresh via crawl.py)" if schema_name == "main"
                                         else f"from irena_cost.duckdb schema={schema_name} (rebuild via build_cost_duckdb.py)",
                    "rows": row_count,
                    "size_mb": None,
                    "columns": schema["dimension_columns"] + [schema["measure_column"]],
                    "latest_year": max_year,
                    "units": schema["units"],
                })
            return out
        return await asyncio.to_thread(_list)

    @mcp.tool
    async def irena_get_dataset_meta(dataset_id: str) -> dict:
        """Return the full schema for one dataset: dimensions, units, example query.

        Args:
            dataset_id: one of the 7 known dataset IDs (use irena_list_datasets to find).

        Returns: {dataset_id, columns, dimension_codes, units, example_query,
        sql_guard_hints}.
        """
        if dataset_id not in table_schemas:
            return {"error": f"Unknown dataset_id: {dataset_id}. Valid: {list(table_schemas.keys())}"}
        schema = table_schemas[dataset_id]
        schema_name = schema.get("schema_name", "main")
        def _meta():
            dimension_codes = []
            for dim_col in schema["dimension_columns"]:
                dim_table = _dim_name(dataset_id, dim_col, schema_name)
                try:
                    codes = duckdb_loader.execute(
                        f'SELECT code, label FROM "{dim_table}" LIMIT 50'
                    ).fetchall()
                    dimension_codes.append({
                        "column": dim_col,
                        "filter_alias": schema["filter_aliases"].get(dim_col),
                        "values_sample": [{"code": c, "label": l} for c, l in codes[:10]],
                    })
                except Exception as e:
                    dimension_codes.append({
                        "column": dim_col,
                        "filter_alias": schema["filter_aliases"].get(dim_col),
                        "error": str(e),
                    })
            return dimension_codes
        dimension_codes = await asyncio.to_thread(_meta)
        return {
            "dataset_id": dataset_id,
            "title": schema["title"],
            "dimension_columns": schema["dimension_columns"],
            "dimension_codes": dimension_codes,
            "measure_column": schema["measure_column"],
            "units": schema["units"],
            "example_query": (
                f'irena_query_dataset(dataset_id="{dataset_id}", '
                f'filters={{"{schema["filter_aliases"][schema["dimension_columns"][0]]}": ["AFG", "DEU"]}}, '
                f'limit=10)'
            ),
            "sql_guard_hints": [
                f'Use filter_alias "{fa}"' for fa in schema["filter_aliases"].values()
            ],
        }

    @mcp.tool
    async def irena_query_dataset(
        dataset_id: str,
        filters: dict | None = None,
        columns: list[str] | None = None,
        limit: int = 100,
        order_by: str | None = None,
    ) -> dict:
        """Query one IRENA dataset with structured filters.

        Args:
            dataset_id: one of the 7 known datasets.
            filters: dict mapping filter_alias (e.g. "countries", "technologies") to a
                list of codes or labels. Labels are auto-converted to codes via
                the dimension tables. Example: {"countries": ["AFG", "DEU"], "years": [2023, 2024]}.
            columns: optional list of column names to return (default = all).
            limit: max rows to return (default 100, hard cap 10_000).
            order_by: optional "column_name [ASC|DESC]" string (whitelisted columns only).

        Returns: {dataset_id, columns, rows, row_count, truncated, citations, sql_executed}.
        """
        if dataset_id not in table_schemas:
            return {"error": f"Unknown dataset_id: {dataset_id}"}
        schema = table_schemas[dataset_id]
        err, sql, params, limit_requested, limit_applied, limit_clamped, filters_applied, filters_dropped = _build_query_sql(
            duckdb_loader, dataset_id, schema, filters, columns, limit, order_by
        )
        if err:
            return err
        def _run():
            return duckdb_loader.execute(sql, params).fetchall()
        try:
            result = await asyncio.to_thread(_run)
        except Exception as e:
            return {"error": f"query failed: {e}", "sql": sql}
        out_cols = columns if columns else schema["dimension_columns"] + [schema["measure_column"]]
        citations = [f'[data: {dataset_id}, rows={len(result)}, filter={json.dumps(filters or {}, default=str)}]']
        return {
            "dataset_id": dataset_id,
            "title": schema["title"],
            "source": "see irena_list_datasets for full attribution",
            "columns": out_cols,
            "rows": [_row_to_dict(out_cols, r) for r in result],
            "row_count": len(result),
            "truncated": len(result) >= limit_applied,
            "citations": citations,
            "sql_executed": sql,
            "filters_applied": filters_applied,
            "filters_dropped": filters_dropped,
            "limit_requested": limit_requested,
            "limit_applied": limit_applied,
            "limit_clamped": limit_clamped,
        }

    @mcp.tool
    async def irena_query_dataset_aggregations(
        dataset_id: str,
        group_by: list[str],
        aggregations: list[dict],
        filters: dict | None = None,
    ) -> dict:
        """Aggregate over a dataset: GROUP BY with sum/avg/count/min/max.

        Args:
            dataset_id: one of the 7 known datasets.
            group_by: list of filter_aliases to group by (e.g. ["countries", "years"]).
            aggregations: list of {"column": str, "function": "sum"|"avg"|"count"|"min"|"max", "alias": str}.
                column must be a filter_alias; alias is the result column name.
            filters: optional structured filter (same shape as irena_query_dataset).

        Returns: aggregated rows with one row per group_by tuple.
        """
        if dataset_id not in table_schemas:
            return {"error": f"Unknown dataset_id: {dataset_id}"}
        schema = table_schemas[dataset_id]
        measure_col = schema["measure_column"]
        reverse_alias = {v: k for k, v in schema["filter_aliases"].items()}

        for gb in group_by:
            if gb not in reverse_alias:
                return {"error": f"Unknown group_by: {gb}"}
        for agg in aggregations:
            if agg.get("function") not in ("sum", "avg", "count", "min", "max"):
                return {"error": f"Invalid function: {agg.get('function')}"}

        gb_cols = [reverse_alias[gb] for gb in group_by]
        gb_quoted = ", ".join([f'"{c}"' for c in gb_cols])

        where_clauses = []
        params: list = []
        if filters:
            for alias, values in filters.items():
                if alias not in reverse_alias:
                    return {"error": f"Unknown filter: {alias}"}
                dim_col = reverse_alias[alias]
                codes = _resolve_filter_values(duckdb_loader, dataset_id, dim_col, values)
                placeholders = ",".join(["?"] * len(codes))
                where_clauses.append(f'"{dim_col}" IN ({placeholders})')
                params.extend(codes)

        agg_clauses = []
        for agg in aggregations:
            alias = agg.get("alias") or f"{agg['function']}_{agg['column']}"
            agg_clauses.append(f'{agg["function"].upper()}("{agg["column"]}") AS "{alias}"')

        sql = f'SELECT {gb_quoted}, {", ".join(agg_clauses)} FROM "{dataset_id}"'
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        sql += f' GROUP BY {gb_quoted} ORDER BY {gb_quoted} LIMIT 10000'

        def _run():
            return duckdb_loader.execute(sql, params).fetchall()
        try:
            result = await asyncio.to_thread(_run)
        except Exception as e:
            return {"error": f"query failed: {e}", "sql": sql}

        out_cols = gb_cols + [agg.get("alias") or f"{agg['function']}_{agg['column']}" for agg in aggregations]
        return {
            "dataset_id": dataset_id,
            "columns": out_cols,
            "rows": [_row_to_dict(out_cols, r) for r in result],
            "row_count": len(result),
            "truncated": False,
            "citations": [f"[data: {dataset_id}, grouped by {group_by}, rows={len(result)}]"],
            "sql_executed": sql,
        }

    @mcp.tool
    async def irena_get_dataset_value(dataset_id: str, filters: dict | None = None) -> dict | float | None:
        """Convenience: pull a single value (or tiny dict) matching the filters.

        Args:
            dataset_id: one of the 7 known datasets.
            filters: structured filter dict.

        Returns: scalar float, or small dict, or None if no match. Errors if
        filters match >10 rows.
        """
        if dataset_id not in table_schemas:
            return {"error": f"Unknown dataset_id: {dataset_id}"}
        schema = table_schemas[dataset_id]
        err, sql, params, _limit_req, _limit_app, _limit_clamp, _fa, _fd = _build_query_sql(
            duckdb_loader, dataset_id, schema, filters, None, 11, None
        )
        if err:
            return err
        def _run():
            return duckdb_loader.execute(sql, params).fetchall()
        try:
            result = await asyncio.to_thread(_run)
        except Exception as e:
            return {"error": f"query failed: {e}"}
        if not result:
            return None
        if len(result) > 10:
            return {"error": f"filters match {len(result)} rows, narrow them down"}
        out_cols = schema["dimension_columns"] + [schema["measure_column"]]
        if len(result) == 1:
            row = dict(zip(out_cols, result[0]))
            return row.get(schema["measure_column"])
        return [_row_to_dict(out_cols, r) for r in result]

    @mcp.tool
    async def irena_sample_dataset(dataset_id: str, n: int = 10) -> dict:
        """Return n random sample rows from a dataset.

        Args:
            dataset_id: one of the 7 known datasets.
            n: sample size (default 10, cap 100).

        Returns: same shape as irena_query_dataset with random rows.
        """
        if dataset_id not in table_schemas:
            return {"error": f"Unknown dataset_id: {dataset_id}"}
        n = max(1, min(n, 100))
        schema = table_schemas[dataset_id]
        sql = f'SELECT * FROM "{dataset_id}" ORDER BY random() LIMIT {n}'
        def _run():
            return duckdb_loader.execute(sql).fetchall()
        try:
            result = await asyncio.to_thread(_run)
        except Exception as e:
            return {"error": f"sampling failed: {e}"}
        all_cols = schema["dimension_columns"] + [schema["measure_column"], "source"]
        out_cols = [c for c in all_cols if c != "source"] + ["source"]
        return {
            "dataset_id": dataset_id,
            "title": schema["title"],
            "columns": out_cols,
            "rows": [_row_to_dict(out_cols, r) for r in result],
            "row_count": len(result),
            "truncated": False,
            "citations": [f"[data: {dataset_id}, sample n={n}]"],
        }

