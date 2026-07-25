"""
Select only the tests affected by changed files.

Examples:
- src/calculator.py -> tests/test_calculator.py
- src/text_utils.py -> tests/test_text_utils.py
- README.md -> no application tests
- shared or unknown Python files -> full test suite
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


TEST_MAP = {
    "src/calculator.py": ["tests/test_calculator.py"],
    "src/text_utils.py": ["tests/test_text_utils.py"],
}

FULL_SUITE_TRIGGERS = {
    "requirements.txt",
    "Jenkinsfile",
    "scripts/select_tests.py",
    "scripts/remediation_agent.py",
}

IGNORED_PREFIXES = (
    "docs/",
)

IGNORED_FILES = {
    "README.md",
}


def normalize_path(path: str) -> str:
    """Convert Windows separators to repository-style forward slashes."""
    return path.strip().replace("\\", "/").lstrip("./")


def get_git_changed_files(base_ref: str) -> list[str]:
    """Return changed files compared with the supplied Git reference."""
    command = ["git", "diff", "--name-only", f"{base_ref}...HEAD"]

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        print(
            f"Could not compare against {base_ref}: {error.stderr.strip()}",
            file=sys.stderr,
        )
        return []

    return [
        normalize_path(line)
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def select_tests(changed_files: list[str]) -> tuple[list[str], list[str]]:
    """
    Return selected tests and reasons.

    Unknown Python, test, dependency, or pipeline changes trigger the full
    suite because their impact may extend beyond one module.
    """
    selected: set[str] = set()
    reasons: list[str] = []
    run_full_suite = False

    for raw_path in changed_files:
        path = normalize_path(raw_path)

        if path in TEST_MAP:
            mapped_tests = TEST_MAP[path]
            selected.update(mapped_tests)
            reasons.append(f"{path} maps to {', '.join(mapped_tests)}")
            continue

        if path.startswith("tests/"):
            selected.add(path)
            reasons.append(f"{path} is a directly changed test")
            continue

        if path in FULL_SUITE_TRIGGERS:
            run_full_suite = True
            reasons.append(f"{path} can affect the entire pipeline")
            continue

        if path in IGNORED_FILES or path.startswith(IGNORED_PREFIXES):
            reasons.append(f"{path} is documentation-only; tests skipped")
            continue

        if path.endswith(".py"):
            run_full_suite = True
            reasons.append(f"{path} is an unmapped Python file")
            continue

        reasons.append(f"{path} has no mapped application tests")

    if run_full_suite:
        return ["tests"], reasons

    return sorted(selected), reasons


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Select tests based on changed files."
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Git reference used for change comparison.",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        help="Changed files supplied manually instead of reading Git.",
    )
    args = parser.parse_args()

    changed_files = (
        [normalize_path(path) for path in args.files]
        if args.files is not None
        else get_git_changed_files(args.base)
    )

    print("Changed files:")
    if changed_files:
        for path in changed_files:
            print(f"  - {path}")
    else:
        print("  - none")

    selected_tests, reasons = select_tests(changed_files)

    print("\nSelection decisions:")
    if reasons:
        for reason in reasons:
            print(f"  - {reason}")
    else:
        print("  - No changed files were detected")

    print("\nSelected tests:")
    if selected_tests:
        for test in selected_tests:
            print(f"  - {test}")
    else:
        print("  - none; application tests skipped")

    # Machine-readable final line for Jenkins.
    print(f"\nSELECTED_TESTS={' '.join(selected_tests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())