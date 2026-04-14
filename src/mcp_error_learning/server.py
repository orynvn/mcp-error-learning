from mcp.server.fastmcp import FastMCP

from mcp_error_learning.database import init_db
from mcp_error_learning.tools.search import search_similar as _search_similar
from mcp_error_learning.tools.record import record_error as _record_error
from mcp_error_learning.tools.patterns import get_patterns as _get_patterns
from mcp_error_learning.tools.outcome import update_outcome as _update_outcome

mcp = FastMCP("mcp-error-learning")

# Initialize DB schema on startup
init_db()


@mcp.tool()
async def search_similar(
    error_message: str,
    stack: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """
    Find similar errors in the knowledge base before starting RCA.
    Call this FIRST when a new bug arrives.

    Args:
        error_message: Stack trace or error message to search for.
        stack: Optional filter — laravel|nextjs|react|nestjs|django|fastapi|vue3.
        limit: Maximum number of results (default: 5).
    """
    return await _search_similar(error_message, stack, limit)


@mcp.tool()
async def record_error(
    symptom: str,
    root_cause: str,
    fix: str,
    stack: str,
    module: str | None = None,
    error_type: str | None = None,
    severity: str = "medium",
    prevention: str | None = None,
    file_path: str | None = None,
    test_added: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """
    Record a new error into the knowledge base after a successful fix.
    Call this after resolving a bug to grow the knowledge base.

    Args:
        symptom: Observable symptom (what was seen).
        root_cause: Root cause analysis result.
        fix: How it was fixed (code snippet or description).
        stack: Tech stack — laravel|nextjs|react|nestjs|django|fastapi|vue3|other.
        module: Module name e.g. AUTH, USER, PAYMENT.
        error_type: logic|null_ref|race_condition|type_mismatch|env_config|n+1|ci_failure.
        severity: low|medium|high|critical (default: medium).
        prevention: Pattern to avoid recurrence.
        file_path: Affected file path (sanitized to relative path automatically).
        test_added: Test case ID e.g. TC-AUTH-001.
        tags: Tags e.g. ["typescript", "null-ref", "async"].
    """
    return await _record_error(
        symptom, root_cause, fix, stack,
        module, error_type, severity, prevention,
        file_path, test_added, tags,
    )


@mcp.tool()
async def get_patterns(
    stack: str,
    module: str | None = None,
    error_type: str | None = None,
) -> list[dict]:
    """
    Get anti-patterns and known pitfalls for a stack/module.
    Implementer agent should call this before writing code to avoid known issues.

    Args:
        stack: Tech stack to query.
        module: Optional module filter.
        error_type: Optional error type filter.
    """
    return await _get_patterns(stack, module, error_type)


@mcp.tool()
async def update_outcome(
    error_id: int,
    was_effective: bool,
    notes: str | None = None,
) -> dict:
    """
    Update effectiveness of a fix suggestion after applying it.
    Improves ranking quality of the knowledge base over time.

    Args:
        error_id: ID returned by search_similar.
        was_effective: True if fix worked, False if not.
        notes: Optional explanation if fix was ineffective.
    """
    return await _update_outcome(error_id, was_effective, notes)
