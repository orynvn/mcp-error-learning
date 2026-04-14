import pytest

from mcp_error_learning.tools.record import record_error, _sanitize, _sanitize_file_path


@pytest.mark.asyncio
async def test_record_returns_id():
    result = await record_error(
        symptom="TypeError: Cannot read property 'id' of undefined",
        root_cause="Missing null check after async operation",
        fix="Add optional chaining: user?.id",
        stack="nextjs",
        module="USER",
        tags=["typescript", "null-ref"],
    )
    assert result["id"] > 0
    assert result["stack"] == "nextjs"
    assert result["module"] == "USER"


@pytest.mark.asyncio
async def test_record_invalid_stack_defaults_to_other():
    result = await record_error(
        symptom="Some error",
        root_cause="Some cause",
        fix="Some fix",
        stack="unknown-stack",
    )
    assert result["stack"] == "other"


@pytest.mark.asyncio
async def test_record_invalid_severity_defaults_to_medium():
    result = await record_error(
        symptom="Some error",
        root_cause="Some cause",
        fix="Some fix",
        stack="laravel",
        severity="ultra-critical",
    )
    assert result["severity"] == "medium"


def test_sanitize_removes_ip():
    result = _sanitize("Connect to 192.168.1.100 failed")
    assert "192.168.1.100" not in result
    assert "[IP]" in result


def test_sanitize_removes_email():
    result = _sanitize("User admin@company.com not found")
    assert "@company.com" not in result
    assert "[EMAIL]" in result


def test_sanitize_removes_credentials():
    result = _sanitize("password=secret123 in config")
    assert "secret123" not in result
    assert "[REDACTED]" in result


def test_sanitize_removes_connection_string():
    result = _sanitize("postgres://admin:secret@db.internal.company.com:5432/prod")
    assert "secret" not in result
    assert "[REDACTED]" in result


def test_sanitize_none_returns_none():
    assert _sanitize(None) is None


def test_sanitize_file_path_extracts_src():
    result = _sanitize_file_path("/Users/john/projects/myapp/src/users/users.service.ts")
    assert result == "src/users/users.service.ts"


def test_sanitize_file_path_extracts_app():
    result = _sanitize_file_path("/home/user/laravel-app/app/Http/Controllers/UserController.php")
    assert result == "app/Http/Controllers/UserController.php"


def test_sanitize_file_path_none():
    assert _sanitize_file_path(None) is None
