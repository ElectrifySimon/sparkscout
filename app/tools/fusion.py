"""Fusion tool — 1 tool. Report search + dataset candidates, no auto-routing.

irena_answer_question searches reports, lists which datasets might answer
the quantitative side of the question, and returns DatasetHint objects.
The LLM picks which dataset to query and calls irena_query_dataset
explicitly. No SQL execution in this tool.

Async tool wrapper so the FastMCP event loop stays unblocked under
concurrent sessions. FTS5 I/O is dispatched via asyncio.to_thread.
"""
import asyncio

from tools.fts5_index import rrf_fuse


def _keyword_hits(text: str, dim_codes: list[str]) -> set:
    """Return set of dimension_codes whose labels appear in text (case-insensitive)."""
    text_lower = text.lower()
    hits = set()
    for code in dim_codes:
        # Convert snake_case to words
        words = code.replace("_", " ").replace("-", " ").lower()
        if words in text_lower:
            hits.add(code)
    return hits


def register(mcp, fts5_index, table_schemas: dict, embeddings=None):
    @mcp.tool
    async def irena_answer_question(question: str, top_k_reports: int = 3) -> dict:
        """Search IRENA reports for the question and surface dataset candidates.

        Hybrid retrieval (BM25 + dense RRF) ranks the report hits; dataset
        candidates are matched by question keywords against dataset titles
        and dimension labels. The LLM picks which dataset to query and
        calls irena_query_dataset explicitly. No SQL execution in this tool.

        Args:
            question: natural language question.
            top_k_reports: number of report search hits to return (default 3, cap 10).

        Returns: {question, reports, citation_block, notes, dataset_candidates,
                retrieval}. `retrieval` summarizes how the hits were sourced
                (BM25 only, dense only, or hybrid).
        """
        top_k_reports = max(1, min(top_k_reports, 10))
        def _search():
            over_fetch = max(top_k_reports * 3, 12)
            bm25_hits = fts5_index.search(question, top_k=over_fetch)
            dense_hits = []
            if embeddings is not None:
                try:
                    dense_hits = embeddings.search(question, top_k=over_fetch)
                except Exception as e:
                    log = __import__("logging").getLogger(__name__)
                    log.warning(f"dense search failed, falling back to BM25: {e}")
            fused = rrf_fuse(bm25_hits, dense_hits, top_k=top_k_reports)
            retrieval = {
                "bm25_only": len(dense_hits) == 0,
                "dense_only": len(bm25_hits) == 0,
                "bm25_count": len(bm25_hits),
                "dense_count": len(dense_hits),
            }
            reports = []
            for h in fused:
                excerpt = h.get("excerpt") or ""
                if not excerpt:
                    excerpt = fts5_index.fetch_excerpt(h["report_id"])
                meta = h.get("metadata") or {}
                reports.append({
                    "report_id": h["report_id"],
                    "chapter": None,
                    "excerpt": excerpt,
                    "line_number": None,
                    "score": h["rrf_score"],
                    "rrf_score": h["rrf_score"],
                    "sources": h["sources"],
                    "matched_terms": [],
                    "title": meta.get("title", ""),
                    "year": meta.get("year"),
                    "citation": meta.get("citation"),
                })
            return reports, retrieval
        result = await asyncio.to_thread(_search)
        reports, retrieval = result
        citation_block = "[reports: " + ", ".join(r["report_id"] for r in reports) + "]" if reports else "[reports: none]"

        # Dataset candidate detection: match question text against dim labels
        # and table titles. No SQL executed.
        candidates = []
        question_lower = question.lower()
        for ds_id, schema in table_schemas.items():
            score = 0
            reasons = []
            # Match against title keywords
            title_words = schema["title"].lower().split()
            title_hits = [w for w in title_words if len(w) > 4 and w in question_lower]
            if title_hits:
                score += len(title_hits) * 2
                reasons.append(f"title mentions: {', '.join(title_hits[:3])}")
            # Match against dim column labels (cheap, no DB hit)
            for dim_col in schema["dimension_columns"]:
                dim_words = dim_col.lower().replace("/", " ").replace("-", " ")
                if dim_words in question_lower:
                    score += 1
                    reasons.append(f"question mentions '{dim_words}'")
            # Match against measure column
            measure_lower = schema["measure_column"].lower()
            if measure_lower.split()[0] in question_lower:
                score += 1
                reasons.append(f"measure is {schema['measure_column']}")
            if score > 0:
                candidates.append({
                    "dataset_id": ds_id,
                    "title": schema["title"],
                    "relevance_score": score,
                    "reason": "; ".join(reasons),
                    "filter_aliases": list(schema["filter_aliases"].keys()),
                    "example_call": f'irena_query_dataset(dataset_id="{ds_id}", filters={{...}}, limit=10)',
                })
        candidates.sort(key=lambda c: c["relevance_score"], reverse=True)

        notes = []
        if not reports:
            notes.append("no reports matched the question text")
        if not candidates:
            notes.append("no datasets seemed relevant; try irena_list_datasets to browse")
        if retrieval["dense_only"]:
            notes.append("BM25 returned no hits; results are dense-only and may need verification")
        if retrieval["bm25_only"]:
            notes.append("dense retrieval was unavailable; results are BM25-only")

        return {
            "question": question,
            "reports": reports,
            "citation_block": citation_block,
            "notes": notes,
            "dataset_candidates": candidates,
            "retrieval": retrieval,
        }
