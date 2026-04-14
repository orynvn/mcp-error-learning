import json
import re

from mcp_error_learning.database import get_connection
from mcp_error_learning.models import RecordResult

_VALID_STACKS = frozenset(
    {"laravel", "nextjs", "react", "nestjs", "django", "fastapi", "vue3", "other"}
)
_VALID_SEVERITIES = frozenset({"low", "medium", "high", "critical"})

_CREDENTIAL_RE = re.compile(
    r"(?i)(password|passwd|secret|token|api[_\-]?key)\s*[:=]\s*\S+"
)
_IP_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_CONN_STRING_RE = re.compile(
    r"(?i)(postgres|mysql|mongodb|redis)://[^@\s]*@[^\s]+"
)
_ABS_PATH_RE = re.compile(r"(/[a-zA-Z0-9_.@\-]+){3,}")
_HOSTNAME_RE = re.compile(r"\b([a-z0-9\-]+\.){2,}[a-z]{2,}\b")


def _sanitize(text: str | None) -> str | None:
    if not text:
        return text
    # Order matters: conn strings before email (to avoid email regex consuming credentials)
    s = _CONN_STRING_RE.sub(r"\1://[REDACTED]@[HOST]", text)
    s = _CREDENTIAL_RE.sub(r"\1=[REDACTED]", s)
    s = _IP_RE.sub("[IP]", s)
    s = _EMAIL_RE.sub("[EMAIL]", s)
    s = _ABS_PATH_RE.sub("[PATH]", s)
    s = _HOSTNAME_RE.sub("[HOST]", s)
    return s


def _sanitize_file_path(path: str | None) -> str | None:
    if not path:
        return path
    # Match a known root dir that appears as its own path component (after / or at start)
    match = re.search(
        r"(?:^|/)((src|app|lib|tests?|packages?|components?|modules?|api|routes?)/.*)",
        path,
    )
    if match:
        return match.group(1).replace("\\", "/")
    # Fallback: filename only
    return path.replace("\\", "/").split("/")[-1]


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
) -> RecordResult:
    if stack not in _VALID_STACKS:
        stack = "other"
    if severity not in _VALID_SEVERITIES:
        severity = "medium"

    tags_json = json.dumps(tags) if tags else None

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO errors
                (stack, module, error_type, severity, symptom, root_cause, fix,
                 prevention, tags, file_path, test_added)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stack,
                module,
                error_type,
                severity,
                _sanitize(symptom),
                _sanitize(root_cause),
                _sanitize(fix),
                _sanitize(prevention),
                tags_json,
                _sanitize_file_path(file_path),
                test_added,
            ),
        )
        new_id = cursor.lastrowid

    return RecordResult(
        id=new_id,
        message=f"Error recorded with ID={new_id}",
        stack=stack,
        module=module,
        severity=severity,
    )
