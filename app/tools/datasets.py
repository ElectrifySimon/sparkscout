"""Dataset tools — 6 tools over the DuckDB file.

Schema discovery via TABLE_SCHEMAS (SSoT in server.py). All queries
built with parameter binding; dataset_id + column names whitelisted
against the schema before SQL is generated. Results are JOINed to
dimension tables so codes like "AFG" come back as "Afghanistan".
"""

import json
from datetime import datetime, timezone


# Common user-supplied aliases for IRENA technologies, mapped to the PxWeb
# numeric codes that the fact tables store. Consulted before the dim-table
# lookup so casual labels like "Solar PV", "Wind", "PV" resolve to the same
# code an analyst would type ("2", "4", etc.).
TECH_ALIASES = {
    "solar pv": "2", "solar photovoltaic": "2", "pv": "2", "photovoltaic": "2",
    "solar": "2", "solar energy": "1", "solar thermal": "3", "solar thermal energy": "3",
    "wind": "4", "wind energy": "4", "onshore wind": "5", "onshore wind energy": "5",
    "offshore wind": "6", "offshore wind energy": "6",
    "hydro": "7", "hydropower": "7", "renewable hydropower": "7", "mixed hydro": "8",
    "mixed hydropower": "8", "pumped hydro": "25", "marine": "9", "marine energy": "9",
    "bioenergy": "10", "biomass": "10", "solid biofuels": "11", "liquid biofuels": "12",
    "gas biofuels": "13", "renewable waste": "14",
    "geothermal": "15", "geothermal energy": "15",
    "fossil fuels": "17", "fossil": "17", "coal": "18", "oil": "19",
    "natural gas": "20", "gas": "20", "nuclear": "21",
    "non-renewable waste": "22",
}


# ---- helpers (also called from server.py via tool definitions) ----

def _dim_name(table_id: str, dim_code: str, schema: str = "main", quoted: bool = True) -> str:
    """dim_{table}_{dim_code_lowercased}. PxWeb uses dim_<table>_<dim_code>.
    quoted=True wraps in DuckDB double-quotes (and qualifies schema when not main).
    quoted=False returns the bare identifier for callers that wrap themselves.
    """
    name = "dim_" + table_id + "_" + dim_code.lower().replace("/", "_").replace(" ", "_").replace("-", "_")
    if not quoted:
        if schema != "main":
            return schema + "." + name
        return name
    if schema != "main":
        return chr(34) + schema + chr(34) + "." + chr(34) + name + chr(34)
    return chr(34) + name + chr(34)


def _fact_name(dataset_id: str, schema_name: str = "main", explicit_table: str | None = None) -> str:
    """Resolve the FROM-clause table reference.

    PxWeb datasets (schema_name == "main") use the dataset_id as the table name directly
    (e.g. "country_capacity"). Cost-corpus datasets (schema_name == "cost") use a
    "fact_<dataset_id>" convention (e.g. "fact_lcoe_weighted"). An explicit_table
    override is honoured if provided in the schema dict.
    """
    if explicit_table:
        name = explicit_table
    elif schema_name == "cost":
        name = "fact_" + dataset_id
    else:
        name = dataset_id
    if schema_name != "main":
        return chr(34) + schema_name + chr(34) + "." + chr(34) + name + chr(34)
    return chr(34) + name + chr(34)


def _row_to_dict(columns: list[str], row: tuple) -> dict:
    return {c: v for c, v in zip(columns, row)}


def _resolve_filter_values(duckdb_loader, dataset_id: str, dim_col: str, values, table_schemas: dict | None = None) -> list:
    """Resolve label strings to codes via the dim table. Falls back to raw values.

    Two-phase match:
      1. Exact label match (case-insensitive) OR exact code match
      2. Substring match (case-insensitive) on label
    Handles "Solar PV" -> "Solar photovoltaic", "Wind" -> "Wind energy",
    "AFG" -> "AFG" code, "2024" -> "24" string code.
    """
    if not isinstance(values, list):
        values = [values]
    schema_name = (table_schemas or {}).get(dataset_id, {}).get("schema_name", "main")
    dim_table = _dim_name(dataset_id, dim_col, schema_name)
    # Plural-safety: try the singular form if the dim table is missing.
    dim_table_singular = None
    if dim_col.endswith("s"):
        singular = dim_col[:-1]
        if singular:
            dim_table_singular = _dim_name(dataset_id, singular)
    # Alias shortcut for Technology dim — but only for PxWeb (main) schema.
    # Cost-corpus uses literal codes like "solar_pv", "onshore_wind" which differ from
    # PxWeb numeric codes ("2", "4"). Apply alias only when the schema is main.
    if dim_col == "Technology" and schema_name == "main":
        aliased: list[str] = []
        for v in values:
            v_lower = str(v).lower().strip()
            code = TECH_ALIASES.get(v_lower)
            if code and code not in aliased:
                aliased.append(code)
        if aliased:
            return aliased
    codes: list[str] = []
    # Build a properly-quoted, optionally schema-qualified bare table reference.
    bare = _dim_name(dataset_id, dim_col, schema_name, quoted=False)
    if schema_name != "main":
        effective_dim_table = chr(34) + schema_name + chr(34) + "." + chr(34) + bare + chr(34)
    else:
        effective_dim_table = chr(34) + bare + chr(34)
    try:
        duckdb_loader.execute("SELECT 1 FROM " + effective_dim_table + " LIMIT 0")
    except Exception:
        if dim_table_singular:
            bare2 = _dim_name(dataset_id, dim_col[:-1], schema_name, quoted=False)
            if schema_name != "main":
                effective_dim_table = chr(34) + schema_name + chr(34) + "." + chr(34) + bare2 + chr(34)
            else:
                effective_dim_table = chr(34) + bare2 + chr(34)
    try:
        # Phase 1: exact (case-insensitive) label OR code match
        lowered = [str(v).lower() for v in values]
        rows = duckdb_loader.execute(
            "SELECT code, label FROM " + effective_dim_table + " WHERE LOWER(label) = ANY(?) OR LOWER(code) = ANY(?)",
            [lowered, lowered],
        ).fetchall()
        for r in rows:
            if r[0] not in codes:
                codes.append(r[0])
        # Phase 2: substring match for any value not yet resolved
        for v in values:
            v_lower = str(v).lower()
            if v_lower in lowered:
                # already matched in Phase 1; double-check we got something
                if any(c.lower() == v_lower for c in codes):
                    continue
            rows = duckdb_loader.execute(
                "SELECT code, label FROM " + effective_dim_table + " WHERE LOWER(label) LIKE ?",
                [f"%{v_lower}%"],
            ).fetchall()
            for r in rows:
                if r[0] not in codes:
                    codes.append(r[0])
    except Exception as e:
        codes = [str(v) for v in values]
    if not codes:
        codes = [str(v) for v in values]
    return codes



def _build_query_sql(duckdb_loader, dataset_id: str, schema: dict, filters: dict | None,
                     columns: list[str] | None, limit: int, order_by: str | None,
                     table_schemas: dict | None = None):
    """Build a parameterized SELECT. Returns (sql, params, columns)."""
    measure_col = schema["measure_column"]
    all_cols = schema["dimension_columns"] + [measure_col]

    if columns is None:
        columns = all_cols
    for c in columns:
        if c not in all_cols:
            return {"error": f"Unknown column: {c}", "available": all_cols}, None, None
    limit = min(max(1, limit), 10_000)

    reverse_alias = {v: k for k, v in schema["filter_aliases"].items()}
    where_clauses = []
    params: list = []
    if filters:
        for alias, values in filters.items():
            if alias not in reverse_alias:
                return {"error": f"Unknown filter: {alias}", "available": list(reverse_alias.keys())}, None, None
            dim_col = reverse_alias[alias]
            codes = _resolve_filter_values(duckdb_loader, dataset_id, dim_col, values, table_schemas)
            placeholders = ",".join(["?"] * len(codes))
            where_clauses.append(f'"{dim_col}" IN ({placeholders})')
            params.extend(codes)

    schema_name = schema.get("schema_name", "main")
    explicit_table = schema.get("table_name")
    quoted_cols = ", ".join([f'"{c}"' for c in columns])
    sql = "SELECT " + quoted_cols + " FROM " + _fact_name(dataset_id, schema_name, explicit_table)
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    if order_by:
        parts = order_by.split()
        col = parts[0]
        direction = parts[1].upper() if len(parts) > 1 else "ASC"
        if col not in all_cols:
            return {"error": f"Unknown order_by column: {col}", "available": all_cols}, None, None
        if direction not in ("ASC", "DESC"):
            return {"error": f"Invalid direction: {direction}"}, None, None
        sql += f' ORDER BY "{col}" {direction}'

    sql += f" LIMIT {int(limit)}"
    return None, sql, params


def register(mcp, duckdb_loader, table_schemas: dict):
    @mcp.tool
    def sparkscout_list_datasets() -> list[dict]:
        """List all 7 IRENA datasets.

        Returns: list of {dataset_id, title, source, snapshot_pulled_at, row_count,
        size_mb, columns, latest_year, units}.
        """
        out = []
        for ds_id, schema in table_schemas.items():
            schema_name = schema.get("schema_name", "main")
            explicit_table = schema.get("table_name")
            fact_ref = _fact_name(ds_id, schema_name, explicit_table)
            measure_col = schema.get("measure_column", "value")
            year_col = "Year" if schema_name == "main" else "year"
            try:
                row_count = duckdb_loader.execute(
                    f"SELECT COUNT(*) FROM {fact_ref}"
                ).fetchone()[0]
            except Exception:
                row_count = None
            try:
                max_year = duckdb_loader.execute(
                    f"SELECT MAX(CAST(\"{year_col}\" AS INTEGER)) FROM {fact_ref}"
                ).fetchone()[0]
            except Exception:
                max_year = None
            try:
                source = duckdb_loader.execute(
                    f"SELECT DISTINCT source FROM {fact_ref} WHERE source IS NOT NULL LIMIT 1"
                ).fetchone()
                source = source[0] if source else "(no source attribution)"
            except Exception:
                source = "(unknown)"
            out.append({
                "dataset_id": ds_id,
                "title": schema["title"],
                "source": source,
                "snapshot_pulled_at": "from irena.duckdb (in-memory; refresh via crawl.py)",
                "rows": row_count,
                "size_mb": None,
                "columns": schema["dimension_columns"] + [schema["measure_column"]],
                "latest_year": max_year,
                "units": schema["units"],
            })
        return out

    @mcp.tool
    def sparkscout_get_dataset_meta(dataset_id: str) -> dict:
        """Return the full schema for one dataset: dimensions, units, example query.

        Args:
            dataset_id: one of the known dataset IDs (use sparkscout_list_datasets to find).

        Returns: {dataset_id, columns, dimension_codes, units, example_query,
        sql_guard_hints}.
        """
        if dataset_id not in table_schemas:
            return {"error": f"Unknown dataset_id: {dataset_id}. Valid: {list(table_schemas.keys())}"}
        schema = table_schemas[dataset_id]
        schema_name = schema.get("schema_name", "main")
        dimension_codes = []
        for dim_col in schema["dimension_columns"]:
            dim_table = _dim_name(dataset_id, dim_col, schema_name)
            try:
                codes = duckdb_loader.execute(
                    f"SELECT code, label FROM {dim_table} LIMIT 50"
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
        return {
            "dataset_id": dataset_id,
            "title": schema["title"],
            "dimension_columns": schema["dimension_columns"],
            "dimension_codes": dimension_codes,
            "measure_column": schema["measure_column"],
            "units": schema["units"],
            "example_query": (
                f'sparkscout_query_dataset(dataset_id="{dataset_id}", '
                f'filters={{"{schema["filter_aliases"][schema["dimension_columns"][0]]}": ["AFG", "DEU"]}}, '
                f'limit=10)'
            ),
            "sql_guard_hints": [
                f'Use filter_alias "{fa}"' for fa in schema["filter_aliases"].values()
            ],
        }

    @mcp.tool
    def sparkscout_query_dataset(
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
        err, sql, params = _build_query_sql(
            duckdb_loader, dataset_id, schema, filters, columns, limit, order_by, table_schemas
        )
        if err:
            return err
        try:
            result = duckdb_loader.execute(sql, params).fetchall()
        except Exception as e:
            return {"error": f"query failed: {e}", "sql": sql}
        out_cols = columns if columns else schema["dimension_columns"] + [schema["measure_column"]]
        citations = [f'[data: {dataset_id}, rows={len(result)}, filter={json.dumps(filters or {}, default=str)}]']
        return {
            "dataset_id": dataset_id,
            "title": schema["title"],
            "source": "see sparkscout_list_datasets for full attribution",
            "columns": out_cols,
            "rows": [_row_to_dict(out_cols, r) for r in result],
            "row_count": len(result),
            "truncated": len(result) >= limit,
            "citations": citations,
            "sql_executed": sql,
        }

    @mcp.tool
    def sparkscout_query_dataset_aggregations(
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
                column is the MEASURE column name (e.g. "Electricity capacity statistics" for capacity tables); discover it via sparkscout_get_dataset_meta. alias is the result column name.
            filters: optional structured filter (same shape as sparkscout_query_dataset).

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

        try:
            result = duckdb_loader.execute(sql, params).fetchall()
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
    def sparkscout_get_dataset_value(dataset_id: str, filters: dict | None = None) -> dict | float | None:
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
        err, sql, params = _build_query_sql(
            duckdb_loader, dataset_id, schema, filters, None, 11, None, table_schemas
        )
        if err:
            return err
        try:
            result = duckdb_loader.execute(sql, params).fetchall()
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
    def sparkscout_sample_dataset(dataset_id: str, n: int = 10) -> dict:
        """Return n random sample rows from a dataset.

        Args:
            dataset_id: one of the 7 known datasets.
            n: sample size (default 10, cap 100).

        Returns: same shape as sparkscout_query_dataset with random rows.
        """
        if dataset_id not in table_schemas:
            return {"error": f"Unknown dataset_id: {dataset_id}"}
        n = max(1, min(n, 100))
        schema = table_schemas[dataset_id]
        sql = f'SELECT * FROM "{dataset_id}" ORDER BY random() LIMIT {n}'
        try:
            result = duckdb_loader.execute(sql).fetchall()
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

