"""Reports tools — 4 tools over the MD folder + FTS5 index.

Async tool wrappers so the FastMCP event loop stays unblocked under
concurrent sessions. FTS5 I/O is dispatched via asyncio.to_thread.
"""

import asyncio


def register(mcp, reports_dir: str, fts5_index):
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
        """BM25 full-text search across the IRENA reports corpus.

        Args:
            query: natural language search query (multi-word OK).
            top_k: number of hits to return (default 5, cap 20).

        Returns: list of {report_id, chapter, excerpt, score, metadata}.
        """
        top_k = max(1, min(top_k, 20))
        def _search():
            return fts5_index.search(query=query, top_k=top_k)
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
