"""SQLite FTS5 index over the IRENA MD reports folder."""

import glob
import logging
import os
import re
import sqlite3

log = logging.getLogger(__name__)


class FTS5Index:
    def __init__(self, reports_dir: str):
        self.reports_dir = reports_dir
        self.conn: sqlite3.Connection | None = None
        # report_id -> {title, year, citation, file_path}
        self.metadata: dict[str, dict] = {}

    def build(self):
        """(Re)build the FTS5 index from scratch."""
        # Use :memory: so the index doesn't persist on disk; small enough.
        # check_same_thread=False: the index is built on the main thread
        # but every search runs via asyncio.to_thread on the FastMCP
        # default thread pool. SQLite's default check_same_thread=True
        # raises "objects created in a thread can only be used in that
        # same thread" when the pool dispatches to a different worker.
        # We don't run concurrent queries on the same connection (each
        # tool call awaits its own to_thread before the next starts),
        # so the relaxed check is safe.
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS reports_fts USING fts5(
                report_id UNINDEXED,
                content,
                tokenize = 'porter unicode61'
            )
            """
        )
        self.metadata = {}
        files = sorted(glob.glob(os.path.join(self.reports_dir, "*.md")))
        for fp in files:
            report_id = os.path.splitext(os.path.basename(fp))[0]
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception as e:
                log.warning(f"failed to read {fp}: {e}")
                continue
            self.conn.execute(
                "INSERT INTO reports_fts(report_id, content) VALUES (?, ?)",
                (report_id, content),
            )
            self.metadata[report_id] = self._extract_metadata(content, fp)
        self.conn.commit()
        log.info(f"FTS5 indexed {len(self.metadata)} reports from {self.reports_dir}")

    def _extract_metadata(self, content: str, fp: str) -> dict:
        """Pull title, year, ISBN, citation from the markdown frontmatter / header."""
        meta: dict = {
            "file_path": fp,
            "title": "",
            "year": None,
            "isbn": None,
            "citation": None,
        }
        # Title = first non-empty H1 or first non-empty line
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                meta["title"] = stripped[2:].strip()
                break
            if stripped:
                meta["title"] = stripped
                break
        # Year: "© IRENA YYYY" or "IRENA (...YYYY,..."
        m = re.search(r"©\s*IRENA\s+(\d{4})", content)
        if m:
            meta["year"] = int(m.group(1))
        # ISBN
        m = re.search(r"ISBN:\s*([\d\-X]+)", content)
        if m:
            meta["isbn"] = m.group(1).strip()
        # Citation
        m = re.search(r"Citation:\s*([^\n]+)", content)
        if m:
            meta["citation"] = m.group(1).strip()
        return meta

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """BM25-ranked search. Returns list of {report_id, chapter, snippet, score}."""
        if self.conn is None:
            return []
        # Escape user query for FTS5 MATCH (wrap in quotes if multi-word,
        # otherwise wildcards will choke on hyphens).
        fts_query = self._escape_fts_query(query)
        try:
            rows = self.conn.execute(
                """
                SELECT report_id, snippet(reports_fts, 1, '[', ']', '…', 12) AS snip,
                       bm25(reports_fts) AS score
                FROM reports_fts
                WHERE reports_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (fts_query, top_k),
            ).fetchall()
        except sqlite3.OperationalError as e:
            log.warning(f"FTS5 query failed for {fts_query!r}: {e}")
            return []
        results = []
        for r in rows:
            report_id, snippet, score = r
            meta = self.metadata.get(report_id, {})
            results.append({
                "report_id": report_id,
                "chapter": None,
                "excerpt": snippet,
                "score": float(score),
                "metadata": meta,
            })
        return results

    @staticmethod
    def _escape_fts_query(q: str) -> str:
        """Wrap multi-word queries in double quotes; escape embedded quotes."""
        q = q.strip()
        if not q:
            return '""'
        if " " in q or "-" in q:
            # Quote and escape internal quotes
            return '"' + q.replace('"', '""') + '"'
        return q

    def fetch_excerpt(self, report_id: str, max_chars: int = 320) -> str:
        """Best-effort excerpt for a hit we know by report_id but not by query.

        Used when RRF surfaces a dense-only result. Returns the first
        paragraph of real content past the frontmatter boilerplate
        (copyright, ISBN, About IRENA, Acknowledgements, Table of
        Contents, Executive Summary headers), capped at max_chars.
        Empty string if the file can't be read.

        Skip rule: walk the file and find the first line that opens a
        numbered chapter, signalled by a heading that starts with a
        digit followed by a period (`# 1.`, `### 2.`, etc.) or by the
        heading `### INTRODUCTION` / `### EXECUTIVE SUMMARY` for
        reports without numeric prefixes. Once we cross that marker,
        take the next 8 non-empty prose lines. If no such marker is
        found (rare, non-IRENA reports), fall back to the prior
        behaviour of the first 8 non-heading lines.
        """
        meta = self.metadata.get(report_id)
        if not meta:
            return ""
        try:
            with open(meta["file_path"], "r", encoding="utf-8", errors="replace") as f:
                body = f.read()
        except Exception:
            return ""
        lines = body.splitlines()

        past_boilerplate = False
        start = 0
        import re
        # Skip past the table of contents (CONTENTS, ABBREVIATIONS,
        # DEFINITIONS) if present. Their headings match INTRODUCTION
        # loosely and the TOC entries are not the body prose.
        in_toc = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.startswith("#"):
                # If we hit a non-heading line, we are out of the TOC
                # even if we never saw an explicit CONTENTS heading.
                in_toc = False
                continue
            if stripped.lower().lstrip("#").strip().startswith(
                ("contents", "table of contents", "abbreviations", "definitions", "foreword", "preface")
            ):
                in_toc = True
                continue
            if in_toc:
                continue
            # Match `# 1.`, `## 2.` (chapter starts with a number and a
            # period, level 1 or 2 only). Level-3+ TOC entries with the
            # same shape (e.g. `###### 1. CONCEPTUAL FRAMING...`) are
            # filtered out by the heading-level restriction.
            m = re.match(r"^#{1,2}\s+\d+\.\s+\S", stripped)
            if m:
                past_boilerplate = True
                start = i + 1
                break
            # Some reports use a named first chapter heading instead.
            # Allow levels 1-3 (e.g. `## INTRODUCTION`, `### EXECUTIVE
            # SUMMARY`); reject deeper levels because those match
            # `#### INTRODUCTION` inside the TOC of reports where
            # CONTENTS, ABBREVIATIONS, DEFINITIONS are emitted at
            # deeper heading levels.
            if re.match(r"^#{1,3}\s+(INTRODUCTION|EXECUTIVE\s+SUMMARY)\b", stripped, re.IGNORECASE):
                past_boilerplate = True
                start = i + 1
                break

        if not past_boilerplate:
            tail = [
                l for l in lines
                if l.strip() and not l.strip().startswith("#")
            ]
            return "\n".join(tail[:8])[:max_chars]

        body_lines = lines[start:]
        prose = [l for l in body_lines if l.strip() and not l.strip().startswith("#")]
        return "\n".join(prose[:8])[:max_chars] if prose else ""

    def doc_count(self) -> int:
        if self.conn is None:
            return 0
        return self.conn.execute("SELECT COUNT(*) FROM reports_fts").fetchone()[0]

    def list_reports(self, year: int | None = None) -> list[dict]:
        out = []
        for report_id, meta in sorted(self.metadata.items()):
            if year is not None and meta.get("year") != year:
                continue
            out.append({
                "report_id": report_id,
                "filename": os.path.basename(meta.get("file_path", "")),
                "title": meta.get("title", ""),
                "year": meta.get("year"),
                "isbn": meta.get("isbn"),
                "citation": meta.get("citation"),
            })
        return out

    def get_report(self, report_id: str, chapter: str | None = None, max_chars: int = 50_000) -> dict | None:
        meta = self.metadata.get(report_id)
        if not meta:
            return None
        try:
            with open(meta["file_path"], "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            return None
        body = content
        if chapter:
            # Match chapter by H2 (## Chapter title)
            pattern = re.compile(
                rf"^##\s+{re.escape(chapter)}.*?(?=^##\s|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE
            )
            m = pattern.search(content)
            if m:
                body = m.group(0)
        truncated = len(body) > max_chars
        if truncated:
            body = body[:max_chars] + f"\n\n[truncated, full report is {len(content)} chars]"
        return {
            "report_id": report_id,
            "title": meta.get("title", ""),
            "citation": meta.get("citation"),
            "chapter": chapter,
            "body": body,
            "truncated": truncated,
            "total_chars": len(content),
        }

    def cite(self, report_id: str, style: str = "irena") -> str:
        meta = self.metadata.get(report_id)
        if not meta:
            return f"Unknown report: {report_id}"
        if style == "irena" and meta.get("citation"):
            return meta["citation"]
        if style == "apa":
            yr = meta.get("year") or "n.d."
            return f"IRENA. ({yr}). {meta.get('title', report_id)}. International Renewable Energy Agency, Abu Dhabi."
        return meta.get("citation") or meta.get("title", report_id)


def rrf_fuse(
    bm25_hits: list[dict],
    dense_hits: list[dict],
    top_k: int,
    k: int = 60,
) -> list[dict]:
    """Reciprocal Rank Fusion of BM25 and dense retrieval results.

    Cormack et al. 2009: rrf_score(d) = sum_{r in rankings} 1 / (k + rank_r(d)).
    k=60 is the value recommended by the original paper and used by most
    production implementations (Elasticsearch, Vespa, etc.).

    Both input lists carry `report_id`. Output is the union, ranked by
    fused score descending. Each hit carries the original bm25 and
    dense ranks (None if absent from that list) and a `sources` list
    showing which retrievers surfaced it.

    `bm25_hits` items are expected to have {report_id, score, excerpt}.
    `dense_hits` items are expected to have {report_id, score}.
    """
    fused: dict[str, dict] = {}
    for rank, h in enumerate(bm25_hits, start=1):
        rid = h["report_id"]
        fused.setdefault(rid, {
            "report_id": rid,
            "bm25_rank": None,
            "dense_rank": None,
            "bm25_score": None,
            "dense_score": None,
            "excerpt": h.get("excerpt", ""),
            "metadata": h.get("metadata", {}),
            "sources": [],
            "rrf_score": 0.0,
        })
        fused[rid]["bm25_rank"] = rank
        fused[rid]["bm25_score"] = h.get("score")
        if "BM25" not in fused[rid]["sources"]:
            fused[rid]["sources"].append("BM25")
    for rank, h in enumerate(dense_hits, start=1):
        rid = h["report_id"]
        fused.setdefault(rid, {
            "report_id": rid,
            "bm25_rank": None,
            "dense_rank": None,
            "bm25_score": None,
            "dense_score": None,
            "excerpt": "",
            "metadata": {},
            "sources": [],
            "rrf_score": 0.0,
        })
        fused[rid]["dense_rank"] = rank
        fused[rid]["dense_score"] = h.get("score")
        if "dense" not in fused[rid]["sources"]:
            fused[rid]["sources"].append("dense")
    for rid, hit in fused.items():
        score = 0.0
        if hit["bm25_rank"] is not None:
            score += 1.0 / (k + hit["bm25_rank"])
        if hit["dense_rank"] is not None:
            score += 1.0 / (k + hit["dense_rank"])
        hit["rrf_score"] = score
    ranked = sorted(fused.values(), key=lambda h: h["rrf_score"], reverse=True)
    return ranked[:top_k]
