from mcp_error_learning.database import get_connection
from mcp_error_learning.models import OutcomeResult


async def update_outcome(
    error_id: int,
    was_effective: bool,
    notes: str | None = None,
) -> OutcomeResult | dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM errors WHERE id = ?", (error_id,)
        ).fetchone()

        if not row:
            return {"error": f"Error with id={error_id} not found"}

        if notes:
            conn.execute(
                """
                UPDATE errors
                SET was_effective = ?,
                    prevention = CASE
                        WHEN prevention IS NULL THEN ?
                        ELSE prevention || ' | ' || ?
                    END,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (1 if was_effective else 0, notes, notes, error_id),
            )
        else:
            conn.execute(
                """
                UPDATE errors
                SET was_effective = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (1 if was_effective else 0, error_id),
            )

    return OutcomeResult(id=error_id, was_effective=was_effective, updated=True)
