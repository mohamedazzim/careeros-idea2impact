"""Public-safe staged-change checks for CareerOS commits."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PREFIXES = (
    ".cursor/",
    ".windsurf/",
    "project-memory/",
    "resume/",
)
PRIVATE_FILES = {"AGENTS.md", "CLAUDE.md"}
SENSITIVE_ENV_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "backend/.env",
    "frontend/.env",
    "frontend/.env.local",
}
PLACEHOLDER_MARKERS = (
    "example",
    "placeholder",
    "replace-me",
    "replace-with",
    "replace_with",
    "change-me",
    "changeme",
    "your-",
    "your_",
    "<",
    "${",
)
SECRET_PATTERNS = (
    ("OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("Bearer token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~-]{24,}\b")),
    ("JWT token", re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b")),
    ("Make webhook", re.compile(r"https://hook\.[A-Za-z0-9.-]*make\.com/[A-Za-z0-9_-]{12,}")),
)
# REQUIRE quotes around the assigned value to prevent variable reference false positives (e.g. settings.API_KEY)
ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|auth[_-]?token|access[_-]?token|client[_-]?secret|"
    r"password|private[_-]?key|secret[_-]?key)\b\s*[:=]\s*['\"]([^\s'\",]{12,})['\"]"
)


def run_git(*args: str, text: bool = True) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=text,
    )


def staged_paths() -> list[str]:
    result = run_git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def staged_bytes(path: str) -> bytes:
    result = run_git("show", f":{path}", text=False)
    return result.stdout if result.returncode == 0 else b""


def is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return not value or any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def scan_text(path: str, content: str) -> list[str]:
    findings: list[str] = []
    for line_number, line in enumerate(content.splitlines(), 1):
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(f"{path}:{line_number}: possible {label}")
        for match in ASSIGNMENT_PATTERN.finditer(line):
            if not is_placeholder(match.group(2)):
                findings.append(f"{path}:{line_number}: possible assigned secret")
    return findings


def main() -> int:
    failures: list[str] = []
    paths = staged_paths()

    # Whitespace errors logged as warnings to prevent baseline failures
    whitespace = run_git("diff", "--cached", "--check")
    if whitespace.returncode != 0:
        print("Warning: staged diff contains whitespace warnings", file=sys.stderr)

    for path in paths:
        lowered = path.lower()
        if path in PRIVATE_FILES or path in SENSITIVE_ENV_NAMES:
            failures.append(f"private or local-only file staged: {path}")
            continue
        if any(lowered.startswith(prefix) for prefix in PRIVATE_PREFIXES):
            failures.append(f"private or local-only path staged: {path}")
            continue

        data = staged_bytes(path)
        if not data or b"\x00" in data[:8192]:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        failures.extend(scan_text(path, text))

    if failures:
        print("pre-commit checks failed:", file=sys.stderr)
        for failure in sorted(set(failures)):
            print(f"  - {failure}", file=sys.stderr)
        print("No secret values were displayed.", file=sys.stderr)
        return 1

    print(f"pre-commit checks passed ({len(paths)} staged paths; no secret values displayed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
