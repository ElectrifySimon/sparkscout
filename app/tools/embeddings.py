"""Embedding client + persistent vector store for IRENA reports.

Storage layout: a separate DuckDB file at IRENA_DATA_DIR/embeddings.duckdb
holding one row per report_id with the 768-dim nomic-embed-text vector as a
DuckDB FLOAT[768] column. Brute-force cosine search in Python; 56 docs is
trivial. Migrate to DuckDB VSS when corpus crosses ~10K.

Model: nomic-embed-text on mg-ollama. Confirmed dimensions: 768.
Context window: 2048 tokens. Whole-document embedding at ~1500-word chunks
fits comfortably.

Why no DuckDB VSS extension here: the add-on costs 12MB in the image and
needs runtime loading. At 56 docs the math is negligible (one matrix-vector
multiply per query). Move to HNSW when corpus crosses ~10K.
"""

import logging
import os
import struct
import time
from urllib import error as urlerr
from urllib import request as urlreq

log = logging.getLogger(__name__)

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_DIM = 768
EMBEDDING_URL = os.environ.get("EMBEDDING_URL", "http://100.101.46.7:11434")
EMBEDDING_TIMEOUT_S = float(os.environ.get("EMBEDDING_TIMEOUT_S", "30"))


class EmbeddingError(RuntimeError):
    """Raised when the embedding backend is unreachable or returns malformed output."""


class Embeddings:
    """Embedding client + vector store wrapped in one class.

    The store is a separate DuckDB file so embeddings survive container
    restarts without re-indexing the corpus.
    """

    def __init__(self, store_path: str, reports_dir: str | None = None,
                 model: str = EMBEDDING_MODEL, url: str = EMBEDDING_URL):
        self.store_path = store_path
        self.reports_dir = reports_dir
        self.model = model
        self.url = url
        self.con = None

    # ---- store lifecycle -------------------------------------------------

    def open(self):
        """Open the embeddings store and ensure schema exists.

        Tries the canonical RW location first (/data/irena/embeddings.duckdb
        on the host path). If the directory is read-only (true for the
        container's /data mount), falls back to a tmpfs path under
        /home/app/.cache. The store survives container restarts only when
        the canonical location is writable; the tmpfs path is ephemeral.

        Read-only paths (pre-computed stores bind-mounted from the host)
        are detected by attempting CREATE TABLE first; if that fails with
        a read-only error and the table already exists, we close the
        connection and reopen in read_only=True mode.
        """
        import duckdb
        candidates = [
            self.store_path,
            "/home/app/.cache/embeddings.duckdb",
            "/tmp/embeddings.duckdb",
        ]
        last_err = None
        for path in candidates:
            try:
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                # Try writable first.
                try:
                    self.con = duckdb.connect(path)
                except Exception as e:
                    # File might not be writable. Try read_only.
                    msg = str(e).lower()
                    is_ro_error = (
                        "read-only" in msg
                        or "read_only" in msg
                        or "permission denied" in msg
                    )
                    if is_ro_error:
                        try:
                            self.con = duckdb.connect(path, read_only=True)
                        except Exception:
                            raise
                        self.store_path = path
                        # Verify the table exists. If not, this isn't a usable
                        # pre-computed store.
                        existing = self.con.execute(
                            "SELECT COUNT(*) FROM information_schema.tables "
                            "WHERE table_name = 'report_embeddings'"
                        ).fetchone()[0]
                        if existing == 0:
                            log.warning(
                                f"store at {path} is read-only and empty"
                            )
                            self.con.close()
                            self.con = None
                            continue
                        log.info(f"opened read-only store at {path}")
                        return self
                    raise
                self.store_path = path
                # Writable path: check if schema exists; if so, skip CREATE.
                existing = self.con.execute(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_name = 'report_embeddings'"
                ).fetchone()[0]
                if existing == 0:
                    self.con.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS report_embeddings (
                            report_id VARCHAR PRIMARY KEY,
                            model VARCHAR NOT NULL,
                            dim INTEGER NOT NULL,
                            vector FLOAT[{EMBEDDING_DIM}] NOT NULL,
                            embedded_at TIMESTAMP NOT NULL
                        )
                        """
                    )
                    self.con.commit()
                else:
                    log.info(f"store at {path} already has schema ({existing} table)")
                break
            except Exception as e:
                last_err = e
                if self.con is not None:
                    try:
                        self.con.close()
                    except Exception:
                        pass
                    self.con = None
                continue
        if self.con is None:
            raise EmbeddingError(
                f"could not open embeddings store in any candidate: {last_err}"
            )
        log.info(f"opened embeddings store at {self.store_path}")
        return self

    def close(self):
        if self.con is not None:
            try:
                self.con.close()
            except Exception:
                pass
            self.con = None

    # ---- corpus indexing -------------------------------------------------

    def index_corpus(self, progress: bool = True) -> dict:
        """Embed every *.md in reports_dir, upserting into the store.

        Re-runs are idempotent: an existing report_id is overwritten with the
        new vector. Use this after --rebuild or when adding new reports.
        """
        if self.con is None:
            self.open()
        import duckdb
        if not self.reports_dir or not os.path.isdir(self.reports_dir):
            raise EmbeddingError(f"reports_dir not found: {self.reports_dir!r}")
        files = sorted(
            os.path.join(self.reports_dir, n)
            for n in os.listdir(self.reports_dir)
            if n.endswith(".md")
        )
        if not files:
            return {"indexed": 0, "skipped": 0, "elapsed_s": 0.0}

        # Batch the embed call. Ollama's /api/embed accepts a list of inputs.
        inputs = []
        ids = []
        for fp in files:
            rid = os.path.splitext(os.path.basename(fp))[0]
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    body = f.read()
            except Exception as e:
                log.warning(f"skip {fp}: {e}")
                continue
            # Truncate to fit 2K context. nomic-embed-tokenizer isn't bundled
            # in the host image; use a conservative char cap (4 chars/token).
            truncated = body[:7500]
            inputs.append(truncated)
            ids.append(rid)

        t0 = time.monotonic()
        vectors = self._embed_batch(inputs)
        elapsed = time.monotonic() - t0

        rows = [
            (rid, self.model, EMBEDDING_DIM, vec, _now_iso())
            for rid, vec in zip(ids, vectors)
        ]
        self.con.executemany(
            """
            INSERT INTO report_embeddings(report_id, model, dim, vector, embedded_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (report_id) DO UPDATE SET
                model = excluded.model,
                dim = excluded.dim,
                vector = excluded.vector,
                embedded_at = excluded.embedded_at
            """,
            rows,
        )
        self.con.commit()
        if progress:
            log.info(f"embedded {len(rows)} reports in {elapsed:.1f}s "
                     f"({len(rows)/max(elapsed,0.001):.1f} docs/s)")
        return {"indexed": len(rows), "skipped": 0, "elapsed_s": elapsed}

    # ---- query -----------------------------------------------------------

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        """Embed query, return top_k report_ids by cosine similarity.

        Returns list of {report_id, score} (cosine in [-1, 1]).
        """
        if self.con is None:
            return []
        vec = self._embed_one(query)
        rows = self.con.execute(
            "SELECT report_id, vector FROM report_embeddings"
        ).fetchall()
        if not rows:
            return []
        scored = []
        for rid, stored in rows:
            stored_list = stored if isinstance(stored, list) else list(stored)
            score = _cosine(vec, stored_list)
            scored.append({"report_id": rid, "score": score})
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:top_k]

    # ---- introspection ---------------------------------------------------

    def stats(self) -> dict:
        """Return index health for /health and irena_embed_health."""
        if self.con is None:
            return {"store": "closed"}
        n = self.con.execute(
            "SELECT COUNT(*) FROM report_embeddings"
        ).fetchone()[0]
        model_row = self.con.execute(
            "SELECT ANY_VALUE(model), ANY_VALUE(dim), MAX(embedded_at) "
            "FROM report_embeddings LIMIT 1"
        ).fetchone()
        return {
            "store": "open",
            "path": self.store_path,
            "model": model_row[0] if model_row else None,
            "dim": model_row[1] if model_row else None,
            "embedded_count": n,
            "last_embedded_at": str(model_row[2]) if model_row and model_row[2] else None,
        }

    def healthcheck(self) -> bool:
        """Round-trip the embedding backend with a tiny probe string.

        Returns True if /api/embed responds with the expected dimension.
        """
        try:
            vec = self._embed_one("ok")
            return len(vec) == EMBEDDING_DIM
        except Exception as e:
            log.warning(f"embedding healthcheck failed: {e}")
            return False

    # ---- HTTP layer ------------------------------------------------------

    def _embed_batch(self, inputs: list[str]) -> list[list[float]]:
        """Call /api/embed with a list of inputs. Server-side batching only.

        Ollama's /api/embed supports a single batched call. Per docs.ollama.com
        the response shape is {model, embeddings: number[][], total_duration,
        load_duration, prompt_eval_count}.
        """
        payload = _json_dumps({"model": self.model, "input": inputs})
        req = urlreq.Request(
            f"{self.url}/api/embed",
            data=payload.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlreq.urlopen(req, timeout=EMBEDDING_TIMEOUT_S) as r:
                body = r.read().decode("utf-8")
        except urlerr.URLError as e:
            raise EmbeddingError(f"embed POST failed: {e}") from e
        try:
            import json as _json
            data = _json.loads(body)
        except Exception as e:
            raise EmbeddingError(f"embed response not JSON: {e}") from e
        vecs = data.get("embeddings")
        if not isinstance(vecs, list) or not vecs:
            raise EmbeddingError(f"embed response missing embeddings: {body[:200]!r}")
        if len(vecs) != len(inputs):
            raise EmbeddingError(
                f"embed response count {len(vecs)} != input count {len(inputs)}"
            )
        for v in vecs:
            if len(v) != EMBEDDING_DIM:
                raise EmbeddingError(
                    f"embed dim {len(v)} != expected {EMBEDDING_DIM}"
                )
        return [list(map(float, v)) for v in vecs]

    def _embed_one(self, text: str) -> list[float]:
        return self._embed_batch([text])[0]


# ---- helpers ---------------------------------------------------------------


def _cosine(a: list[float], b: list[float]) -> float:
    """Plain-Python cosine similarity for two equal-length vectors.

    Both nomic-embed-text vectors and our stored FLOAT[768] come out
    L2-normalized at model output, so dot product == cosine. Still, do the
    full math here so the function is robust to non-normalized inputs.
    """
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(obj) -> str:
    import json
    return json.dumps(obj, separators=(",", ":"))
