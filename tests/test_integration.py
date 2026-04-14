import pytest

from mcp_error_learning.tools.record import record_error
from mcp_error_learning.tools.search import search_similar
from mcp_error_learning.tools.outcome import update_outcome
from mcp_error_learning.tools.patterns import get_patterns


@pytest.mark.asyncio
async def test_full_debugger_flow():
    """Simulate: search (empty) → record → search again → update_outcome."""
    # 1. No results yet
    results = await search_similar("KeyError user_id Django session", stack="django")
    assert results == []

    # 2. Record after manual fix
    rec = await record_error(
        symptom="KeyError: 'user_id' in session data",
        root_cause="Session expired before request completed",
        fix="Use request.session.get('user_id') with a default instead of session['user_id']",
        stack="django",
        module="AUTH",
        error_type="logic",
        severity="high",
        prevention="Always use .get() with a default for session keys",
        tags=["django", "session", "keyerror"],
    )
    assert rec["id"] > 0

    # 3. Search again — should now find it
    results = await search_similar("KeyError session Django", stack="django")
    assert len(results) > 0

    # 4. Mark fix as effective
    outcome = await update_outcome(rec["id"], was_effective=True)
    assert outcome["updated"] is True
    assert outcome["was_effective"] is True


@pytest.mark.asyncio
async def test_update_outcome_not_found_returns_error():
    result = await update_outcome(error_id=99999, was_effective=False)
    assert "error" in result


@pytest.mark.asyncio
async def test_update_outcome_with_notes():
    rec = await record_error(
        symptom="500 Internal Server Error on /api/users",
        root_cause="Unhandled exception in view",
        fix="Wrap in try/except",
        stack="fastapi",
    )
    outcome = await update_outcome(
        rec["id"], was_effective=False, notes="Fix only worked in dev, not prod"
    )
    assert outcome["updated"] is True
    assert outcome["was_effective"] is False


@pytest.mark.asyncio
async def test_get_patterns_returns_learned_pitfalls():
    """Implementer flow: get_patterns before writing code."""
    await record_error(
        symptom="N+1 query in user list endpoint",
        root_cause="Missing eager loading for related models",
        fix="Use select_related('profile') in queryset",
        stack="django",
        module="USER",
        error_type="n+1",
        prevention="Always eager-load related models in list views",
        tags=["django", "n+1", "orm"],
    )

    patterns = await get_patterns(stack="django", module="USER")
    assert isinstance(patterns, list)
    assert len(patterns) > 0
    learned = [p for p in patterns if p["type"] == "learned"]
    assert len(learned) > 0


@pytest.mark.asyncio
async def test_get_patterns_empty_stack():
    patterns = await get_patterns(stack="vue3")
    assert isinstance(patterns, list)
