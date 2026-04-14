import pytest

from mcp_error_learning.tools.record import record_error
from mcp_error_learning.tools.search import search_similar
from mcp_error_learning.database import get_connection


@pytest.mark.asyncio
async def test_search_finds_recorded_error():
    await record_error(
        symptom="TypeError: Cannot read property 'id' of undefined",
        root_cause="Missing null check",
        fix="Add optional chaining: user?.id",
        stack="nextjs",
        tags=["typescript", "null-ref"],
    )
    results = await search_similar("Cannot read property undefined", stack="nextjs")
    assert len(results) > 0
    assert results[0]["stack"] == "nextjs"


@pytest.mark.asyncio
async def test_search_returns_empty_list_when_no_match():
    results = await search_similar("xyzzy completelyrandom gibberish", stack="laravel")
    assert isinstance(results, list)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_search_without_stack_filter():
    await record_error(
        symptom="NullPointerException in UserService",
        root_cause="Uninitialized object used before assignment",
        fix="Add null check before accessing object",
        stack="nestjs",
    )
    results = await search_similar("NullPointerException UserService")
    assert isinstance(results, list)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_search_increments_times_referenced():
    rec = await record_error(
        symptom="UnboundLocalError: local variable referenced before assignment",
        root_cause="Variable used before assignment in conditional block",
        fix="Initialize variable before the if block",
        stack="fastapi",
    )
    error_id = rec["id"]

    await search_similar("UnboundLocalError variable referenced before assignment", stack="fastapi")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT times_referenced FROM errors WHERE id = ?", (error_id,)
        ).fetchone()
    assert row["times_referenced"] >= 1


@pytest.mark.asyncio
async def test_search_respects_limit():
    for i in range(10):
        await record_error(
            symptom=f"TypeError undefined property access number {i}",
            root_cause="Null reference",
            fix="Add null check",
            stack="react",
        )
    results = await search_similar("TypeError undefined property", stack="react", limit=3)
    assert len(results) <= 3
