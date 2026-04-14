# mcp-error-learning

> MCP server tích lũy kiến thức từ lịch sử lỗi và fix, giúp Copilot Debugger agent ngày càng thông minh hơn — không đoán mù mà tra cứu từ kinh nghiệm thực tế.

**Phase 1:** SQLite + FTS5, stdio transport, single project, local machine.

---

## Cơ chế hoạt động

```
Bug mới đến
  ↓
[MCP] search_similar(error_message, stack)
  ├── Tìm thấy match → Suggest fix từ DB → Apply → update_outcome()
  └── Không có → RCA bình thường → Fix → record_error() → KB lớn dần
```

---

## Cài đặt

**Yêu cầu:** Python 3.12+

```bash
git clone https://github.com/orynvn/mcp-error-learning.git
cd mcp-error-learning
pip install -e .
```

VS Code tự detect server qua `.vscode/mcp.json` (xem cấu hình bên dưới).

---

## MCP Tools

| Tool | Khi nào gọi | Mô tả |
|---|---|---|
| `search_similar` | Đầu tiên khi bug đến | Tìm lỗi tương tự trong KB |
| `record_error` | Sau khi fix xong | Lưu lỗi mới vào KB |
| `get_patterns` | Trước khi viết code | Lấy anti-patterns của stack/module |
| `update_outcome` | Sau khi apply fix từ DB | Đánh dấu fix có hiệu quả không |

### `search_similar`

```python
search_similar(
    error_message: str,   # Stack trace hoặc error message
    stack: str | None,    # Filter: laravel|nextjs|react|nestjs|django|fastapi|vue3
    limit: int = 5,
)
```

### `record_error`

```python
record_error(
    symptom: str,         # Triệu chứng quan sát được
    root_cause: str,      # Nguyên nhân gốc rễ
    fix: str,             # Cách fix
    stack: str,           # laravel|nextjs|react|nestjs|django|fastapi|vue3|other
    module: str | None,   # AUTH | USER | PAYMENT | ...
    error_type: str | None,  # logic|null_ref|race_condition|type_mismatch|env_config|n+1|ci_failure
    severity: str = "medium",  # low|medium|high|critical
    prevention: str | None,
    file_path: str | None,  # Tự động sanitize về relative path
    test_added: str | None, # TC-MODULE-NNN
    tags: list[str] | None,
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
    error_id: int,
    was_effective: bool,
    notes: str | None,
)
```

---

## Cấu hình VS Code (`.vscode/mcp.json`)

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

`record_error` tự động xóa trước khi lưu:
- Absolute paths → chỉ giữ relative pattern (`src/users/...`)
- Credentials, API keys, tokens
- IP addresses, email addresses
- Connection strings có credentials
- Hostnames nội bộ

---

## Chạy tests

```bash
pip install -e ".[dev]"
pytest
```

---

## Cấu trúc

```
mcp-error-learning/
├── pyproject.toml
├── src/
│   └── mcp_error_learning/
│       ├── __init__.py
│       ├── __main__.py        # python -m mcp_error_learning
│       ├── server.py          # FastMCP server + 4 tools
│       ├── database.py        # SQLite + FTS5 schema
│       ├── models.py          # TypedDicts
│       └── tools/
│           ├── search.py      # search_similar
│           ├── record.py      # record_error + sanitization
│           ├── patterns.py    # get_patterns
│           └── outcome.py     # update_outcome
├── data/
│   └── .gitkeep               # errors.db tạo ở đây lúc runtime
└── tests/
    ├── conftest.py
    ├── test_record.py
    ├── test_search.py
    └── test_integration.py
```

---

## Roadmap

| Phase | Storage | Transport | Scope |
|---|---|---|---|
| **Phase 1** (hiện tại) | SQLite + FTS5 | stdio | Single project, local |
| **Phase 2** | PostgreSQL + pgvector | HTTP | Team, cross-project, semantic search |
| **Phase 3** | Vector DB (Qdrant) | HTTP | Auto-categorize, confidence score, AI suggestions |
