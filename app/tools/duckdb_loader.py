"""DuckDB read-only connection manager. SIGHUP-triggered reload."""

import logging
import duckdb

log = logging.getLogger(__name__)


class DuckDBLoader:
    def __init__(self, path: str, cost_path: str | None = None):
        self.path = path
        self.cost_path = cost_path
        self.con = None

    def open(self):
        """Open a read-only DuckDB connection. ATTACH cost DB as `cost` schema if available."""
        self.con = duckdb.connect(self.path, read_only=True)
        tables = self.con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
        log.info(f"DuckDB open, {len(tables)} main tables")
        if self.cost_path:
            try:
                self.con.execute(f"ATTACH '{self.cost_path}' AS cost (READ_ONLY)")
                cost_tables = self.con.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='cost'"
                ).fetchall()
                log.info(f"Cost DB attached, {len(cost_tables)} cost tables")
            except Exception as e:
                log.warning(f"Cost DB not attached: {e}")

    def reload(self):
        if self.con is not None:
            try:
                self.con.close()
            except Exception:
                pass
        self.con = None
        self.open()

    def execute(self, sql: str, params: list | None = None):
        if self.con is None:
            raise RuntimeError("DuckDB connection is not open")
        if params:
            return self.con.execute(sql, params)
        return self.con.execute(sql)

    def query_df(self, sql: str, params: list | None = None):
        import pandas as pd
        return self.execute(sql, params).df()
