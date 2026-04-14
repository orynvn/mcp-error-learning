import json

from mcp_error_learning.database import get_connection
from mcp_error_learning.models import ErrorRecord


def _sanitize_fts_query(query: str) -> str:
    """Convert a raw error message into a safe FTS5 query."""
    # Strip FTS5 special characters that break parsing
    for ch in ("(", ")", ":", "^", '"', "'", "*"):
        query = query.replace(ch, " ")

    # Pick the most meaningful words (length > 2, limit to 10 terms)
    words = [w for w in query.split() if len(w) > 2][:10]
    if not words:
        return '""'

    # OR-join quoted terms for broader matching
    return " OR ".join(f'"{w}"' for w in words)


def _row_to_dict(row) -> ErrorRecord:
    tags_raw = row["tags"]
    try:
        tags: list[str] = json.loads(tags_raw) if tags_raw else []
    except (json.JSONDecodeError, TypeError):
        tags = []

    return ErrorRecord(
        id=row["id"],
        created_at=row["created_at"],
        stack=row["stack"],
        module=row["module"],
        error_type=row["error_type"],
        severity=row["severity"],
        symptom=row["symptom"],
        root_cause=row["root_cause"],
        fix=row["fix"],
        prevention=row["prevention"],
        tags=tags,
        file_path=row["file_path"],
        test_added=row["test_added"],
        times_referenced=row["times_referenced"],
        was_effective=bool(row["was_effective"]),
    )


async def search_similar(
    error_message: str,
    stack: str | None = None,
    limit: int = 5,
) -> list[ErrorRecord]:
    fts_query = _sanitize_fts_query(error_message)

    with get_connection() as conn:
        if stack:
            rows = conn.execute(
                """
                SELECT e.*
                FROM errors_fts fts
                JOIN errors e ON e.id = fts.rowid
                WHERE errors_fts MATCH ? AND e.stack = ?
                ORDER BY fts.rank
                LIMIT ?
                """,
                (fts_query, stack, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT e.*
                FROM errors_fts fts
                JOIN errors e ON e.id = fts.rowid
                WHERE errors_fts MATCH ?
                ORDER BY fts.rank
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()

        if rows:
            ids = [row["id"] for row in rows]
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE errors SET times_referenced = times_referenced + 1 WHERE id IN ({placeholders})",
                ids,
            )

        return [_row_to_dict(row) for row in rows]
