# MCP Error Learning Server — System Design & Roadmap

> **Mục tiêu:** Xây dựng một MCP server tích lũy kiến thức từ lịch sử lỗi và fix, giúp Copilot agent ngày càng thông minh hơn khi debug — không phải đoán mù mà tra cứu từ kinh nghiệm thực tế.

---

## Vấn đề cần giải quyết

GitHub Copilot rất mạnh ở pattern recognition trong context hiện tại, nhưng **không có long-term memory**:

- Cùng một lỗi có thể lặp lại nhiều lần trong dự án mà agent không biết.
- Kiến thức về "lỗi này tương tự BUG-047, fix bằng cách X" biến mất sau mỗi session.
- Lessons learned từ debug chỉ sống trong `ERRORS.md` (text file, không searchable theo semantic).
- Không có cơ chế chia sẻ knowledge giữa các dự án hoặc các thành viên team.

**MCP Error Learning Server** giải quyết bằng cách trở thành "bộ nhớ ngoài có cấu trúc" cho Debugger agent.

---

## Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────┐
│  GitHub Copilot (Debugger Agent)                │
│                                                  │
│  "Lỗi mới đến → tìm xem đã gặp chưa?"           │
└──────────────────┬──────────────────────────────┘
                   │ MCP Protocol (stdio/HTTP)
                   ▼
┌─────────────────────────────────────────────────┐
│  mcp-error-learning server                      │
│                                                  │
│  Tools:                                          │
│  ├── search_similar(error, stack)               │
│  ├── record_error(symptom, cause, fix, ...)     │
│  ├── get_patterns(stack, module)                │
│  └── update_outcome(id, was_effective)          │
└──────────────────┬──────────────────────────────┘
                   │
         ┌─────────┴──────────┐
         ▼                    ▼
  [Phase 1]             [Phase 2+]
  SQLite (local)        PostgreSQL + pgvector
  Full-text search      Semantic similarity
  Single project        Cross-project / Team
```

---

## Phase 1 — Local SQLite (stdio transport)

**Mục tiêu:** Validate concept với setup đơn giản nhất có thể. Single project, local machine.

**Tech stack:**
- Python 3.12+
- `mcp` SDK (`pip install mcp`)
- `sqlite3` (built-in)
- Full-text search qua SQLite FTS5

**Transport:** `stdio` — VS Code giao tiếp qua stdin/stdout, không cần network.

### Database Schema

```sql
-- Bảng chính lưu lỗi
CREATE TABLE errors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),

    -- Classification
    stack       TEXT    NOT NULL,   -- 'laravel' | 'nextjs' | 'react' | 'nestjs' | 'django' | 'fastapi'
    module      TEXT,               -- 'AUTH' | 'USER' | 'PAYMENT' | ...
    error_type  TEXT,               -- 'logic' | 'null_ref' | 'race_condition' | 'type_mismatch' | 'env_config' | 'n+1' | 'ci_failure'
    severity    TEXT    DEFAULT 'medium', -- 'low' | 'medium' | 'high' | 'critical'

    -- Error details
    symptom     TEXT    NOT NULL,   -- Triệu chứng quan sát được
    root_cause  TEXT    NOT NULL,   -- Nguyên nhân gốc rễ
    fix         TEXT    NOT NULL,   -- Cách fix (code snippet hoặc mô tả)
    prevention  TEXT,               -- Pattern để tránh tái diễn
    tags        TEXT,               -- JSON array: ["n+1", "eager-load", "eloquent"]

    -- Context
    file_path   TEXT,               -- File bị lỗi (sanitized, no absolute path)
    test_added  TEXT,               -- TC-MODULE-NNN nếu có

    -- Effectiveness tracking
    times_referenced INTEGER DEFAULT 0,
    was_effective    INTEGER DEFAULT 1  -- 1 = fix hiệu quả, 0 = cần revisit
);

-- FTS5 index cho full-text search
CREATE VIRTUAL TABLE errors_fts USING fts5(
    symptom,
    root_cause,
    fix,
    tags,
    content='errors',
    content_rowid='id'
);

-- Trigger sync FTS khi insert/update
CREATE TRIGGER errors_after_insert AFTER INSERT ON errors BEGIN
    INSERT INTO errors_fts(rowid, symptom, root_cause, fix, tags)
    VALUES (new.id, new.symptom, new.root_cause, new.fix, new.tags);
END;

CREATE TRIGGER errors_after_update AFTER UPDATE ON errors BEGIN
    INSERT INTO errors_fts(errors_fts, rowid, symptom, root_cause, fix, tags)
    VALUES ('delete', old.id, old.symptom, old.root_cause, old.fix, old.tags);
    INSERT INTO errors_fts(rowid, symptom, root_cause, fix, tags)
    VALUES (new.id, new.symptom, new.root_cause, new.fix, new.tags);
END;

-- Bảng patterns (anti-patterns đã biết theo stack)
CREATE TABLE patterns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stack       TEXT    NOT NULL,
    pattern     TEXT    NOT NULL,   -- Mô tả pattern
    example     TEXT,               -- Code example xấu
    fix_example TEXT,               -- Code example tốt
    source_error_id INTEGER REFERENCES errors(id)
);
```

### MCP Tools

#### `search_similar`
Tìm lỗi tương tự trong DB trước khi bắt đầu RCA.

```python
@server.tool()
async def search_similar(
    error_message: str,     # Stack trace hoặc error message
    stack: str | None,      # Filter theo stack (optional)
    limit: int = 5,         # Số kết quả tối đa
) -> list[dict]:
    """
    Tìm errors tương tự trong knowledge base.
    Trả về list các errors với similarity score, fix suggestion, và lessons.
    Debugger agent gọi tool này ĐẦU TIÊN trước khi làm RCA.
    """
```

Output format:
```json
[
  {
    "id": 42,
    "similarity": "high",
    "symptom": "TypeError: Cannot read property 'id' of undefined",
    "root_cause": "Missing null check sau async operation",
    "fix": "Add optional chaining: user?.id",
    "prevention": "Luôn check null sau await operations trong TypeScript",
    "times_referenced": 3,
    "tags": ["typescript", "null-ref", "async"]
  }
]
```

#### `record_error`
Lưu error mới sau khi đã fix thành công.

```python
@server.tool()
async def record_error(
    symptom: str,
    root_cause: str,
    fix: str,
    stack: str,
    module: str | None,
    error_type: str | None,
    severity: str = "medium",
    prevention: str | None,
    file_path: str | None,   # Sẽ được sanitize (chỉ giữ relative path pattern)
    test_added: str | None,
    tags: list[str] | None,
) -> dict:
    """
    Record error mới vào knowledge base.
    Debugger agent gọi tool này sau khi fix thành công.
    """
```

#### `get_patterns`
Lấy danh sách anti-patterns phổ biến cho một stack/module.

```python
@server.tool()
async def get_patterns(
    stack: str,
    module: str | None,
    error_type: str | None,
) -> list[dict]:
    """
    Lấy patterns và anti-patterns phổ biến.
    Implementer agent có thể gọi trước khi viết code để avoid known pitfalls.
    """
```

#### `update_outcome`
Cập nhật kết quả sau khi apply fix suggestion từ DB.

```python
@server.tool()
async def update_outcome(
    error_id: int,
    was_effective: bool,
    notes: str | None,    # Tại sao không hiệu quả nếu was_effective=False
) -> dict:
    """
    Đánh dấu fix suggestion có hiệu quả không.
    Giúp ranking quality của knowledge base theo thời gian.
    """
```

### File structure (Phase 1)

```
mcp-error-learning/
├── README.md               # Hướng dẫn setup và sử dụng
├── DESIGN.md               # File này
├── pyproject.toml          # Package config (uv / pip)
├── src/
│   └── mcp_error_learning/
│       ├── __init__.py
│       ├── server.py       # MCP server entry point
│       ├── database.py     # SQLite connection + migrations
│       ├── tools/
│       │   ├── search.py   # search_similar tool
│       │   ├── record.py   # record_error tool
│       │   ├── patterns.py # get_patterns tool
│       │   └── outcome.py  # update_outcome tool
│       └── models.py       # Data classes / TypedDicts
├── data/
│   └── .gitkeep            # DB file được tạo runtime (errors.db)
└── tests/
    ├── test_search.py
    ├── test_record.py
    └── test_integration.py
```

### .vscode/mcp.json config (Phase 1)

```json
"error-learning": {
  "type": "stdio",
  "command": "python",
  "args": ["-m", "mcp_error_learning"],
  "cwd": "${workspaceFolder}/mcp-error-learning",
  "env": {
    "DB_PATH": "${workspaceFolder}/mcp-error-learning/data/errors.db"
  },
  "description": "Error Learning MCP — knowledge base lỗi local (Phase 1: SQLite)",
  "installRequired": true,
  "installCommand": "cd mcp-error-learning && pip install -e ."
}
```

---

## Phase 2 — Team/Shared (HTTP transport + pgvector)

**Mục tiêu:** Chia sẻ knowledge base giữa nhiều developer và nhiều dự án.

**Thay đổi so với Phase 1:**
- Transport: `stdio` → `http` (deploy như REST API)
- Storage: SQLite → PostgreSQL + `pgvector` extension
- Search: FTS5 → semantic search (OpenAI embeddings hoặc local model)
- Auth: API key per project

**Semantic search hoạt động thế nào:**
```
Error message đến
  → Generate embedding vector (1536 dims với text-embedding-3-small)
  → Cosine similarity search với pgvector: ORDER BY embedding <=> query_vec LIMIT 5
  → Kết quả: lỗi "similar meaning" dù error message khác hoàn toàn
```

Ví dụ: "NullReferenceException ở UserService" vs "Cannot read property of undefined trong userService.ts" → cùng pattern null-ref, tìm được nhau dù khác stack.

**New tools trong Phase 2:**
- `search_cross_project(error, project_filter)` — tìm từ knowledge base toàn tổ chức
- `export_knowledge(stack, format)` — export để share hoặc backup
- `get_team_patterns(team_id)` — patterns phổ biến nhất của team

---

## Phase 3 — Smart Suggestions

**Mục tiêu:** Agent không chỉ tra cứu mà còn học và dự đoán.

**Capabilities:**
- **Auto-categorize** error khi record (không cần user label `error_type`).
- **Suggest regression test** dựa trên lịch sử: "Lỗi này thường tái diễn ở module X, add test case TC-AUTH-045 để phòng ngừa".
- **Confidence scoring**: "Fix này hiệu quả 87% với 13 cases tương tự".
- **Pattern clustering**: tự phát hiện anti-patterns mới chưa được ghi nhận.
- **Integration với security-auditor**: nếu bug liên quan security, tự thêm vào security checklist.

---

## Privacy & Security

### Sanitization rules (áp dụng từ Phase 1)

Trước khi `record_error`, Debugger agent PHẢI sanitize:
- Xóa absolute paths → chỉ giữ relative pattern (`src/users/users.service.ts`)
- Xóa variable values khỏi stack trace (giữ error type + line pattern)
- Xóa credentials, tokens, email, IP addresses trong error message
- Xóa tên database, server hostnames

### Ví dụ sanitization

```
# Raw (KHÔNG record)
Error: ECONNREFUSED connect to postgres://admin:secret123@db.company.com:5432/prod_db

# Sanitized (OK để record)
Error: ECONNREFUSED connect to PostgreSQL
Fix: Check DATABASE_URL env var, ensure DB container is running
```

---

## Integration với workflow hiện tại

### Debugger agent flow sau khi có MCP

```
Bug mới đến
  ↓
[MCP] search_similar(error_message, stack)
  ├── Tìm thấy match (similarity: high)
  │   → Suggest fix từ DB, agent verify rồi apply
  │   → [MCP] update_outcome(id, was_effective=true)
  │
  └── Không tìm thấy / low similarity
      → Chạy RCA bình thường (Reproduce → Analyze → Fix)
      → [MCP] record_error(symptom, root_cause, fix, ...)
      → Append ERRORS.md với MCP ID reference
```

### Implementer agent flow

```
Trước khi viết code cho module X:
  ↓
[MCP] get_patterns(stack, module=X)
  → Nhận list known pitfalls cho module này
  → Tránh ngay từ đầu (prevention > fix)
```

---

## Implementation Plan

### Sprint 1 (Phase 1 MVP)
- [ ] Setup project structure + `pyproject.toml`
- [ ] Database module (`database.py` với schema + migrations)
- [ ] `record_error` tool
- [ ] `search_similar` tool (FTS5)
- [ ] MCP server entry point (`server.py`)
- [ ] Config trong `.vscode/mcp.json`
- [ ] Update Debugger agent prompt để dùng MCP tools

### Sprint 2 (Phase 1 Complete)
- [ ] `get_patterns` tool
- [ ] `update_outcome` tool
- [ ] Auto-sanitization trong `record_error`
- [ ] Unit tests
- [ ] Export patterns → sync với `.context/ERRORS.md`

### Sprint 3 (Phase 2 Foundation)
- [ ] Migrate từ SQLite → PostgreSQL
- [ ] HTTP transport thay stdin/stdout
- [ ] OpenAI embeddings cho semantic search
- [ ] API key auth

### Sprint 4+ (Phase 2 & 3)
- [ ] Cross-project search
- [ ] Auto-categorization
- [ ] Confidence scoring
- [ ] Dashboard UI (optional)
