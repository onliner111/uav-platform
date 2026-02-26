from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
IGNORED_DIRS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache"}


def _iter_markdown_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.md")
        if not any(part in IGNORED_DIRS for part in path.parts)
    ]


def main() -> int:
    violations: list[str] = []
    for file_path in _iter_markdown_files(REPO_ROOT):
        raw = file_path.read_bytes()
        rel_path = file_path.relative_to(REPO_ROOT)
        try:
            raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            violations.append(f"{rel_path}: invalid UTF-8 ({exc})")
            continue
        if raw.startswith(b"\xef\xbb\xbf"):
            violations.append(f"{rel_path}: UTF-8 BOM is not allowed")

    if violations:
        print("Markdown UTF-8 check failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Markdown UTF-8 check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
