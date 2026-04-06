#!/usr/bin/env python3
"""Rename Python project template placeholders to the current repository name.

Usage:
    python scripts/rename_template.py --dry-run  # preview changes without writing
    python scripts/rename_template.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

TEMPLATE_HYPHEN = "python-project-template"
TEMPLATE_UNDERSCORE = "python_project_template"
TEMPLATE_SPACES = "python project template"
TEMPLATE_UPPER_UNDERSCORE = "PYTHON_PROJECT_TEMPLATE"

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


def derive_names(repo_root: Path) -> tuple[str, str, str]:
    repo_name = repo_root.name
    package_name = repo_name.replace("-", "_")
    spaced_name = repo_name.replace("-", " ")
    return repo_name, package_name, spaced_name


def is_text_file(path: Path) -> bool:
    try:
        path.read_text(encoding="utf-8")
        return True
    except (UnicodeDecodeError, OSError):
        return False


def find_matches(content: str, replacements: list[tuple[str, str]]) -> list[tuple[int, str, int]]:
    matches: list[tuple[int, str, int]] = []
    old_values = [old for old, _ in replacements]
    for line_no, line in enumerate(content.splitlines(), start=1):
        for old in old_values:
            count = line.count(old)
            if count > 0:
                matches.append((line_no, old, count))
    return matches


def replace_in_file(path: Path, replacements: list[tuple[str, str]], dry_run: bool) -> tuple[int, int]:
    original = path.read_text(encoding="utf-8")
    matches = find_matches(original, replacements)
    if not matches:
        return 0, 0

    for line_no, token, count in matches:
        print(f"found {path}:{line_no} token={token!r} count={count}")

    updated = original

    for old, new in replacements:
        updated = updated.replace(old, new)

    if dry_run:
        print(f"[DRY-RUN] update {path}")
    else:
        path.write_text(updated, encoding="utf-8")
        print(f"updated {path}")

    return 1, len(matches)


def rename_package_dir(repo_root: Path, new_package_name: str, dry_run: bool) -> bool:
    src_dir = repo_root / "src"
    old_dir = src_dir / TEMPLATE_UNDERSCORE
    new_dir = src_dir / new_package_name

    if not old_dir.exists() or old_dir == new_dir:
        return False

    if new_dir.exists():
        raise FileExistsError(f"Cannot rename {old_dir} to {new_dir}: target exists")

    if dry_run:
        print(f"[DRY-RUN] rename {old_dir} -> {new_dir}")
    else:
        old_dir.rename(new_dir)
        print(f"renamed {old_dir} -> {new_dir}")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes only")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    repo_name, package_name, spaced_name = derive_names(repo_root)

    replacements = [
        (TEMPLATE_HYPHEN, repo_name),
        (TEMPLATE_UNDERSCORE, package_name),
        (TEMPLATE_SPACES, spaced_name),
        (TEMPLATE_UPPER_UNDERSCORE, package_name.upper()),
    ]

    changed_files = 0
    total_matches = 0
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path == Path(__file__).resolve():
            continue
        if not is_text_file(path):
            continue
        file_changed, match_count = replace_in_file(path, replacements, args.dry_run)
        changed_files += file_changed
        total_matches += match_count

    renamed_dir = rename_package_dir(repo_root, package_name, args.dry_run)

    print(
        "Summary:",
        f"files_changed={changed_files}",
        f"matches_found={total_matches}",
        f"package_dir_renamed={renamed_dir}",
        sep=" ",
    )


if __name__ == "__main__":
    main()
