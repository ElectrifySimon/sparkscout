#!/usr/bin/env python3
"""embed_corpus.py — one-shot corpus embedder for SparkScout reports.

Usage:
    uv run --with duckdb python3 tools/embed_corpus.py --print-config
    uv run --with duckdb python3 tools/embed_corpus.py --reindex
    uv run --with duckdb python3 tools/embed_corpus.py --healthcheck

Reads the same env vars the MCP server uses (IRENA_DATA_DIR,
EMBEDDING_URL, EMBEDDING_MODEL) so the offline CLI matches the runtime.

Run --reindex after adding new reports to /data/reports. Idempotent:
existing report_ids are overwritten with the fresh vector. The embedding
store is a separate DuckDB file (embeddings.duckdb) so reindexing doesn't
touch the canonical irena.duckdb.
"""

import argparse
import logging
import os
import sys
import time

# Make the app package importable when run from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from tools.embeddings import Embeddings, EMBEDDING_MODEL, EMBEDDING_DIM

log = logging.getLogger("embed_corpus")


def _reports_dir() -> str:
    return os.environ.get("IRENA_REPORTS_DIR", "/data/reports")


def _store_path() -> str:
    data_dir = os.environ.get("IRENA_DATA_DIR", "/data/irena")
    return os.path.join(data_dir, "embeddings.duckdb")


def _embeddings() -> Embeddings:
    return Embeddings(
        store_path=_store_path(),
        reports_dir=_reports_dir(),
    )


def cmd_print_config(_args):
    s = _embeddings()
    print(f"reports_dir     : {_reports_dir()}")
    print(f"store_path      : {s.store_path}")
    print(f"embedding_url   : {s.url}")
    print(f"embedding_model : {s.model}")
    print(f"embedding_dim   : {EMBEDDING_DIM}")
    return 0


def cmd_reindex(args):
    s = _embeddings()
    s.open()
    t0 = time.monotonic()
    res = s.index_corpus(progress=not args.quiet)
    elapsed = time.monotonic() - t0
    print(f"ok: indexed {res['indexed']} reports in {elapsed:.1f}s "
          f"({res['indexed']/max(elapsed,0.001):.1f} docs/s)")
    return 0


def cmd_healthcheck(_args):
    s = _embeddings()
    s.open()
    ok = s.healthcheck()
    stats = s.stats()
    print(f"backend_ok      : {ok}")
    print(f"model           : {stats.get('model')}")
    print(f"dim             : {stats.get('dim')}")
    print(f"embedded_count  : {stats.get('embedded_count')}")
    print(f"last_embedded   : {stats.get('last_embedded_at')}")
    return 0 if ok else 2


def cmd_stats(_args):
    s = _embeddings()
    s.open()
    print(s.stats())
    return 0


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("--print-config", help="Show config without touching the store")
    p_reindex = sub.add_parser("--reindex", help="Embed every report in IRENA_REPORTS_DIR")
    p_reindex.add_argument("--quiet", action="store_true")
    sub.add_parser("--healthcheck", help="Round-trip a probe to the embedding backend")
    sub.add_parser("--stats", help="Print index stats")
    args = ap.parse_args()
    return {
        "--print-config": cmd_print_config,
        "--reindex": cmd_reindex,
        "--healthcheck": cmd_healthcheck,
        "--stats": cmd_stats,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
