"""Optional pgvector support.

The pipeline stores passage embeddings as portable JSON arrays so the app runs on
SQLite with zero setup. When PostgreSQL has the `vector` extension available this
module adds a native `embedding_vec` column and an IVFFlat index, enabling ANN
search without changing application code paths.

Everything here is best-effort and non-fatal: if pgvector is unavailable the
application keeps working with the JSON representation.
"""
from __future__ import annotations

from sqlalchemy import text

from app.core.logging import log


def ensure_pgvector(engine) -> dict:
    if engine.dialect.name != "postgresql":
        return {"enabled": False, "reason": "not a postgresql database"}
    with engine.begin() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception as exc:  # noqa: BLE001
            log.warning("pgvector_unavailable", extra={"event": "pgvector", "extra_data": str(exc)[:200]})
            return {"enabled": False, "reason": "extension not available"}

        conn.execute(
            text(
                "ALTER TABLE evidence_passages "
                "ADD COLUMN IF NOT EXISTS embedding_vec vector(1536)"
            )
        )
        try:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_passages_embedding_vec "
                    "ON evidence_passages USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 100)"
                )
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("pgvector_index_failed", extra={"event": "pgvector_index", "extra_data": str(exc)[:200]})
            return {"enabled": True, "indexed": False, "reason": str(exc)[:160]}
    log.info("pgvector_enabled", extra={"event": "pgvector"})
    return {"enabled": True, "indexed": True}


def similarity_search(conn, query_vector: list[float], limit: int = 8) -> list[tuple[str, float]]:
    """Nearest passages by cosine distance (requires pgvector)."""
    literal = "[" + ",".join(f"{v:.6f}" for v in query_vector) + "]"
    rows = conn.execute(
        text(
            "SELECT id, 1 - (embedding_vec <=> CAST(:q AS vector)) AS similarity "
            "FROM evidence_passages WHERE embedding_vec IS NOT NULL "
            "ORDER BY embedding_vec <=> CAST(:q AS vector) LIMIT :limit"
        ),
        {"q": literal, "limit": limit},
    ).all()
    return [(row[0], float(row[1])) for row in rows]
