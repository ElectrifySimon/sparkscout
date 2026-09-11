"""Reports tools — 4 tools over the MD folder + FTS5 index.

Async tool wrappers so the FastMCP event loop stays unblocked under
concurrent sessions. FTS5 I/O is dispatched via asyncio.to_thread.
"""

import asyncio

from tools.fts5_index import rrf_fuse


def register(mcp, reports_dir: str, fts5_index, embeddings=None):
    @mcp.tool
    async def irena_list_reports(year: int | None = None) -> list[dict]:
        """List IRENA reports in the corpus.

        Args:
            year: optional ISO year (e.g. 2026) to filter by.

        Returns: list of {report_id, filename, title, year, isbn, citation}.
        """
        def _list():
            return fts5_index.list_reports(year=year)
        return await asyncio.to_thread(_list)

    @mcp.tool
    async def irena_get_report(report_id: str, chapter: str | None = None, max_chars: int = 50_000) -> dict:
        """Fetch a single IRENA report's markdown body.

        Args:
            report_id: report filename without ".md" (from irena_list_reports).
            chapter: optional H2 heading to extract just that chapter.
            max_chars: truncate body to this many chars (default 50k).

        Returns: {report_id, title, citation, chapter, body, truncated, total_chars}.
        """
        def _get():
            return fts5_index.get_report(report_id, chapter=chapter, max_chars=max_chars)
        result = await asyncio.to_thread(_get)
        if result is None:
            return {"error": f"Unknown report_id: {report_id}"}
        return result

    @mcp.tool
    async def irena_search_reports(query: str, top_k: int = 5) -> list[dict]:
        """Hybrid search across the IRENA reports corpus (BM25 + dense, fused via RRF).

        Combines FTS5 BM25 keyword matches with semantic similarity from
        nomic-embed-text vectors. Reciprocal Rank Fusion (Cormack 2009) merges
        the two rankings. Falls back to BM25-only if the embedding store is
        unavailable.

        Args:
            query: natural language search query (multi-word OK).
            top_k: number of hits to return (default 5, cap 20).

        Returns: list of {report_id, excerpt, rrf_score, sources, bm25_rank,
                bm25_score, dense_rank, dense_score, metadata}. `sources` lists
                which retrievers surfaced the hit ("BM25", "dense", or both).
        """
        top_k = max(1, min(top_k, 20))
        def _search():
            # Pull more than top_k from each retriever so RRF has good coverage
            # at the cut-off (Cormack 2009 recommends ~2x or more for the union).
            over_fetch = max(top_k * 3, 20)
            bm25_hits = fts5_index.search(query=query, top_k=over_fetch)
            dense_hits = []
            if embeddings is not None:
                try:
                    dense_hits = embeddings.search(query=query, top_k=over_fetch)
                except Exception as e:
                    # Embedding backend down — degrade gracefully to BM25-only.
                    log = __import__("logging").getLogger(__name__)
                    log.warning(f"dense search failed, falling back to BM25: {e}")
            fused = rrf_fuse(bm25_hits, dense_hits, top_k=top_k)
            # Backfill excerpts for dense-only hits (BM25 hits already carry one).
            hits = []
            for h in fused:
                excerpt = h.get("excerpt") or ""
                if not excerpt:
                    excerpt = fts5_index.fetch_excerpt(h["report_id"])
                hits.append({
                    "report_id": h["report_id"],
                    "chapter": None,
                    "excerpt": excerpt,
                    "rrf_score": h["rrf_score"],
                    "sources": h["sources"],
                    "bm25_rank": h["bm25_rank"],
                    "bm25_score": h["bm25_score"],
                    "dense_rank": h["dense_rank"],
                    "dense_score": h["dense_score"],
                    "metadata": h.get("metadata", {}),
                })
            return hits
        return await asyncio.to_thread(_search)

    @mcp.tool
    async def irena_cite(report_id: str, style: str = "irena") -> str:
        """Return a formatted citation string for a report.

        Args:
            report_id: report filename without ".md".
            style: "irena" (default, uses the report's own citation block) or "apa".

        Returns: the citation string. Returns 'Unknown report: <id>' if id not found.
        """
        def _cite():
            return fts5_index.cite(report_id, style=style)
        return await asyncio.to_thread(_cite)

    @mcp.tool
    async def irena_embed_health() -> dict:
        """Return embedding-store health and stats.

        Returns dict with: store ("open"|"closed"), path, model, dim,
        embedded_count, last_embedded_at, backend_ok (round-trip
        healthcheck). Use this to confirm the embedding layer is alive
        without pulling every report's vector.
        """
        if embeddings is None:
            return {"store": "disabled"}
        def _stats():
            stats = embeddings.stats()
            stats["backend_ok"] = embeddings.healthcheck()
            return stats
        return await asyncio.to_thread(_stats)
