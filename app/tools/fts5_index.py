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
