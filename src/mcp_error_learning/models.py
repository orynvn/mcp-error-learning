from typing import TypedDict


class ErrorRecord(TypedDict, total=False):
    id: int
    created_at: str
    updated_at: str
    stack: str
    module: str | None
    error_type: str | None
    severity: str
    symptom: str
    root_cause: str
    fix: str
    prevention: str | None
    tags: list[str]
    file_path: str | None
    test_added: str | None
    times_referenced: int
    was_effective: bool


class PatternRecord(TypedDict, total=False):
    id: int
    stack: str
    pattern: str
    example: str | None
    fix_example: str | None
    source_error_id: int | None


class RecordResult(TypedDict):
    id: int
    message: str
    stack: str
    module: str | None
    severity: str


class OutcomeResult(TypedDict):
    id: int
    was_effective: bool
    updated: bool
