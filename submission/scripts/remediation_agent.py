"""
Formatting-remediation agent for the Agent-Optimized CI assignment.

The agent handles one narrowly defined failure class:
Black formatting failures in Python source files under src/.

It reads a Black failure log and one source file, asks Claude for a
formatting-only correction, and prints the proposed full file content.
It does not write files, modify tests, change dependencies, or merge code.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import anthropic


ALLOWED_SOURCE_DIR = Path("src")
ALLOWED_SUFFIX = ".py"


def validate_source_path(source_path: Path) -> None:
    """Reject files outside src/ and non-Python files."""
    resolved_source = source_path.resolve()
    resolved_allowed_dir = ALLOWED_SOURCE_DIR.resolve()

    if resolved_source.suffix != ALLOWED_SUFFIX:
        raise ValueError("Only Python source files may be remediated.")

    if resolved_allowed_dir not in resolved_source.parents:
        raise ValueError("The remediation agent may only access files under src/.")


def load_text(path: Path) -> str:
    """Read a UTF-8 text file with a clear error if it is missing."""
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    return path.read_text(encoding="utf-8")


def build_fix_schema() -> dict:
    """Return the strict JSON schema required from Claude."""
    return {
        "type": "object",
        "properties": {
            "failure_class": {"type": "string"},
            "root_cause": {"type": "string"},
            "fix_description": {"type": "string"},
            "fixed_file_content": {"type": "string"},
        },
        "required": [
            "failure_class",
            "root_cause",
            "fix_description",
            "fixed_file_content",
        ],
        "additionalProperties": False,
    }


def propose_formatting_fix(
    build_log: str,
    source_code: str,
    source_path: Path,
) -> dict:
    """Ask Claude for a formatting-only correction."""
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"]
    )

    response = client.messages.create(
        model=os.environ.get("MODEL", "claude-haiku-4-5"),
        max_tokens=2048,
        system=(
            "You are a narrowly scoped CI remediation agent. "
            "You may handle only Black formatting failures in one Python file "
            "under src/. Preserve program behavior exactly. Return the complete "
            "formatted source file. Do not change tests, dependencies, Jenkins "
            "configuration, environment variables, comments unrelated to "
            "formatting, function names, function signatures, or logic. "
            "Do not propose fixes for syntax errors, test failures, security "
            "issues, dependency failures, or any failure class other than "
            "Black formatting. If the log is not a Black formatting failure, "
            "state that the failure class is unsupported and return the "
            "original source unchanged."
        ),
        output_config={
            "format": {
                "type": "json_schema",
                "schema": build_fix_schema(),
            }
        },
        messages=[
            {
                "role": "user",
                "content": (
                    f"Black check log:\n```\n{build_log}\n```\n\n"
                    f"Allowed source file: {source_path.as_posix()}\n"
                    f"Current source:\n```python\n{source_code}\n```"
                ),
            }
        ],
    )

    text_block = next(
        block.text for block in response.content if block.type == "text"
    )
    return json.loads(text_block)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Propose a formatting-only remediation."
    )
    parser.add_argument(
        "--log",
        default="format_log.txt",
        help="Path to the Black failure log.",
    )
    parser.add_argument(
        "--source",
        default="src/text_utils.py",
        help="Python source file under src/.",
    )
    args = parser.parse_args()

    log_path = Path(args.log)
    source_path = Path(args.source)

    validate_source_path(source_path)

    build_log = load_text(log_path)
    source_code = load_text(source_path)

    fix = propose_formatting_fix(
        build_log=build_log,
        source_code=source_code,
        source_path=source_path,
    )

    print(f"Failure class: {fix['failure_class']}")
    print(f"Root cause: {fix['root_cause']}")
    print(f"Fix: {fix['fix_description']}")
    print(f"File: {source_path.as_posix()}")
    print("\n--- Proposed formatted file (no file changed) ---")
    print(fix["fixed_file_content"])
    print("\nHuman approval is required before applying this proposal.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())