"""Fusion tool — 1 tool. Report search + dataset candidates, no auto-routing.

irena_answer_question searches reports, lists which datasets might answer
the quantitative side of the question, and returns DatasetHint objects.
The LLM picks which dataset to query and calls irena_query_dataset
explicitly. No SQL execution in this tool.

Async tool wrapper so the FastMCP event loop stays unblocked under
concurrent sessions. FTS5 I/O is dispatched via asyncio.to_thread.
"""

import asyncio


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


def register(mcp, fts5_index, table_schemas: dict):
    @mcp.tool
    async def irena_answer_question(question: str, top_k_reports: int = 3) -> dict:
        """Search IRENA reports for the question and surface dataset candidates.

        No dataset auto-routing. Returns report search hits and DatasetHint[]
        listing plausible datasets; the LLM picks and calls irena_query_dataset.

        Args:
            question: natural language question.
            top_k_reports: number of report search hits to return (default 3, cap 10).

        Returns: {question, reports, citation_block, notes, dataset_candidates}.
        """
        top_k_reports = max(1, min(top_k_reports, 10))
        def _search():
            return fts5_index.search(question, top_k=top_k_reports)
        hits = await asyncio.to_thread(_search)
        reports = []
        for h in hits:
            meta = h.get("metadata", {})
            reports.append({
                "report_id": h["report_id"],
                "chapter": h.get("chapter"),
                "excerpt": h.get("excerpt"),
                "line_number": None,
                "score": h.get("score"),
                "matched_terms": [],
                "title": meta.get("title", ""),
                "year": meta.get("year"),
                "citation": meta.get("citation"),
            })
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

        return {
            "question": question,
            "reports": reports,
            "citation_block": citation_block,
            "notes": notes,
            "dataset_candidates": candidates,
        }
