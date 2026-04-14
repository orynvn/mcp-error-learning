import pytest

from mcp_error_learning.database import init_db


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Each test gets a fresh isolated SQLite database."""
    db_path = tmp_path / "test_errors.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    init_db()
    yield db_path
