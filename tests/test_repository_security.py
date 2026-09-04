from __future__ import annotations

import re
from pathlib import Path


_TEXT_SUFFIXES = {".md", ".txt", ".toml", ".py", ".ps1", ".yml", ".yaml", ".json", ".ini", ".cfg"}
_SENSITIVE_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}"),
    re.compile(r"\b(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.(?:\d{1,3}\.)\d{1,3})\b"),
    re.compile(r"(?i)[A-Za-z]:\\Users\\[^\\\s]+"),
    re.compile(r"(?i)/home/[^/\s]+/"),
)


def test_public_repository_has_no_obvious_local_secrets_or_personal_paths():
    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        if any(part in {".git", ".pytest_cache", "__pycache__"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in _SENSITIVE_PATTERNS:
            if pattern.search(text):
                failures.append(f"{path.relative_to(root)} matches {pattern.pattern}")
    assert not failures, "Potential secret/local-path leak(s):\n" + "\n".join(failures)
