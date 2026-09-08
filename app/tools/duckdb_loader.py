"""DuckDB read-only connection manager. SIGHUP-triggered reload."""

import logging
import duckdb

log = logging.getLogger(__name__)


class DuckDBLoader:
    def __init__(self, path: str):
        self.path = path
        self.con = None

    def open(self):
        """Open a read-only DuckDB connection."""
        self.con = duckdb.connect(self.path, read_only=True)
        # Sanity check: can we list tables?
        tables = self.con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
        log.info(f"DuckDB open, {len(tables)} tables")

    def reload(self):
        """Close and reopen (used after irena.duckdb is replaced on disk)."""
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
        """Return a pandas DataFrame (used by aggregations tool)."""
        import pandas as pd
        return self.execute(sql, params).df()
