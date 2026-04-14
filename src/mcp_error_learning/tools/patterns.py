from mcp_error_learning.database import get_connection


async def get_patterns(
    stack: str,
    module: str | None = None,
    error_type: str | None = None,
) -> list[dict]:
    with get_connection() as conn:
        # Named patterns from the patterns table
        pattern_rows = conn.execute(
            "SELECT * FROM patterns WHERE stack = ? ORDER BY id DESC LIMIT 20",
            (stack,),
        ).fetchall()

        # Learned anti-patterns: most-referenced effective fixes per stack/module
        params: list = [stack]
        filters = "stack = ? AND was_effective = 1"
        if module:
            filters += " AND module = ?"
            params.append(module)
        if error_type:
            filters += " AND error_type = ?"
            params.append(error_type)
        params.append(10)

        error_rows = conn.execute(
            f"""
            SELECT symptom, root_cause, fix, prevention, times_referenced, error_type
            FROM errors
            WHERE {filters}
            ORDER BY times_referenced DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    result: list[dict] = [
        {
            "type": "pattern",
            "pattern": row["pattern"],
            "example": row["example"],
            "fix_example": row["fix_example"],
        }
        for row in pattern_rows
    ]

    result += [
        {
            "type": "learned",
            "error_type": row["error_type"],
            "symptom": row["symptom"],
            "root_cause": row["root_cause"],
            "fix": row["fix"],
            "prevention": row["prevention"],
            "times_seen": row["times_referenced"],
        }
        for row in error_rows
    ]

    return result
