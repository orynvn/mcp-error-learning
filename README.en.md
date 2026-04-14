# mcp-error-learning

> An MCP server that accumulates knowledge from past errors and fixes, making the Copilot Debugger agent smarter over time — looking up proven solutions instead of guessing from scratch.

**Phase 1:** SQLite + FTS5, stdio transport, single project, local machine.

---

## How It Works

```
New bug arrives
  ↓
[MCP] search_similar(error_message, stack)
  ├── Match found → Suggest fix from DB → Apply → update_outcome()
  └── No match   → Normal RCA → Fix → record_error() → KB grows
```

---

## Installation

**Requirements:** Python 3.12+

```bash
git clone https://github.com/orynvn/mcp-error-learning.git
cd mcp-error-learning
pip install -e .
```

VS Code auto-detects the server via `.vscode/mcp.json` (see configuration below).

---

## MCP Tools

| Tool | When to call | Description |
|---|---|---|
| `search_similar` | First, when a bug arrives | Find similar errors in the KB |
| `record_error` | After a successful fix | Save a new error to the KB |
| `get_patterns` | Before writing code | Get anti-patterns for a stack/module |
| `update_outcome` | After applying a DB suggestion | Mark whether the fix was effective |

### `search_similar`

```python
search_similar(
    error_message: str,   # Stack trace or error message to search for
    stack: str | None,    # Filter: laravel|nextjs|react|nestjs|django|fastapi|vue3
    limit: int = 5,       # Max results (default: 5)
)
```

### `record_error`

```python
record_error(
    symptom: str,            # Observable symptom
    root_cause: str,         # Root cause analysis result
    fix: str,                # How it was fixed (code snippet or description)
    stack: str,              # laravel|nextjs|react|nestjs|django|fastapi|vue3|other
    module: str | None,      # e.g. AUTH | USER | PAYMENT
    error_type: str | None,  # logic|null_ref|race_condition|type_mismatch|env_config|n+1|ci_failure
    severity: str = "medium",   # low|medium|high|critical
    prevention: str | None,     # Pattern to avoid recurrence
    file_path: str | None,      # Auto-sanitized to relative path
    test_added: str | None,     # TC-MODULE-NNN if a test was added
    tags: list[str] | None,     # e.g. ["typescript", "null-ref", "async"]
)
```

### `get_patterns`

```python
get_patterns(
    stack: str,
    module: str | None,
    error_type: str | None,
)
```

### `update_outcome`

```python
update_outcome(
    error_id: int,        # ID returned by search_similar
    was_effective: bool,  # True if the fix worked
    notes: str | None,    # Optional explanation if fix was ineffective
)
```

---

## VS Code Configuration (`.vscode/mcp.json`)

```json
"error-learning": {
  "type": "stdio",
  "command": "python",
  "args": ["-m", "mcp_error_learning"],
  "cwd": "${workspaceFolder}/mcp-error-learning",
  "env": {
    "DB_PATH": "${workspaceFolder}/mcp-error-learning/data/errors.db"
  }
}
```

---

## Privacy & Sanitization

`record_error` automatically strips sensitive data before saving:
- Absolute paths → kept as relative pattern only (`src/users/...`)
- Credentials, API keys, tokens
- IP addresses and email addresses
- Connection strings containing credentials
- Internal hostnames

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```

---

## Project Structure

```
mcp-error-learning/
├── pyproject.toml
├── README.md              # Vietnamese
├── README.en.md           # English (this file)
├── src/
│   └── mcp_error_learning/
│       ├── __init__.py
│       ├── __main__.py        # python -m mcp_error_learning entry point
│       ├── server.py          # FastMCP server + 4 registered tools
│       ├── database.py        # SQLite + FTS5 schema, triggers, init
│       ├── models.py          # TypedDicts for type safety
│       └── tools/
│           ├── search.py      # search_similar — FTS5 full-text search
│           ├── record.py      # record_error + sanitization pipeline
│           ├── patterns.py    # get_patterns — learned + named patterns
│           └── outcome.py     # update_outcome — effectiveness tracking
├── data/
│   └── .gitkeep               # errors.db is created here at runtime
└── tests/
    ├── conftest.py            # Isolated temp DB per test
    ├── test_record.py         # record_error + sanitization unit tests
    ├── test_search.py         # search_similar unit tests
    └── test_integration.py   # Full debugger flow integration tests
```

---

## Roadmap

| Phase | Storage | Transport | Scope |
|---|---|---|---|
| **Phase 1** (current) | SQLite + FTS5 | stdio | Single project, local |
| **Phase 2** | PostgreSQL + pgvector | HTTP | Team, cross-project, semantic search |
| **Phase 3** | Vector DB (Qdrant) | HTTP | Auto-categorize, confidence scoring, AI suggestions |
