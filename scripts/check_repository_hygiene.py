from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

FORBIDDEN_DIRECTORIES = {
    ".next",
    ".playwright-cli",
    ".python-deps",
    ".test-tmp",
    ".venv",
    "__pycache__",
    "data",
    "indextts2",
    "legacy",
    "logs",
    "node_modules",
    "output",
    "tmp",
    "uploads",
}

FORBIDDEN_FILES = {
    ".env",
    "findings.md",
    "progress.md",
    "task_plan.md",
    "命令文件.md",
    "全方位审查报告.md",
}

FORBIDDEN_SUFFIXES = {
    ".db",
    ".log",
    ".mp3",
    ".mp4",
    ".pyc",
    ".sqlite",
    ".sqlite3",
    ".wav",
}

TEXT_PATTERNS = {
    "private Windows user path": re.compile(r"C:\\Users\\", re.IGNORECASE),
    "workspace drive path": re.compile(r"E:\\aaaa"),
    "Codex runtime path": re.compile(r"codex-runtimes", re.IGNORECASE),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI-style key": re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    "GitHub token": re.compile(r"(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}"),
    "Google API key": re.compile(r"AIza[A-Za-z0-9_-]{20,}"),
}

TEXT_SUFFIXES = {
    ".cjs",
    ".css",
    ".example",
    ".json",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".svg",
    ".ts",
    ".tsx",
    ".txt",
    ".yml",
    ".yaml",
}


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def repository_files() -> tuple[list[Path], bool]:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z"],
            check=False,
            capture_output=True,
        )
    except OSError:
        result = None

    if result is not None and result.returncode == 0:
        tracked = [ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]
        return tracked, True

    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(ROOT).parts
        if any(part in FORBIDDEN_DIRECTORIES or part == ".git" for part in relative_parts[:-1]):
            continue
        if path.name.startswith(".env") and not path.name.endswith(".example"):
            continue
        files.append(path)
    return files, False


def main() -> int:
    errors: list[str] = []
    files, from_git = repository_files()
    for path in sorted(files):
        if path == SELF:
            continue
        relative_parts = path.relative_to(ROOT).parts
        forbidden_parts = FORBIDDEN_DIRECTORIES.intersection(relative_parts[:-1])
        if from_git and forbidden_parts:
            errors.append(f"forbidden tracked directory: {relative(path)}")
        if path.name in FORBIDDEN_FILES or (from_git and path.name.startswith(".env") and not path.name.endswith(".example")):
            errors.append(f"forbidden file: {relative(path)}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden artifact: {relative(path)}")
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".editorconfig", ".gitattributes", ".gitignore", "LICENSE"}:
            continue
        try:
            content = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        for label, pattern in TEXT_PATTERNS.items():
            if pattern.search(content):
                errors.append(f"{label}: {relative(path)}")

    if errors:
        print("Repository hygiene check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Repository hygiene check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
