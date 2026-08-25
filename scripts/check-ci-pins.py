#!/usr/bin/env python3
"""Reject mutable third-party references in release-critical build files."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHA_REF = re.compile(r"^[0-9a-f]{40}$")
DIGEST_REF = re.compile(r"@sha256:[0-9a-f]{64}(?:\s|$)")


def workflow_errors() -> list[str]:
    errors: list[str] = []
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        for line_number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
            match = re.search(r"\buses:\s*([^\s#]+)", line)
            if not match:
                continue
            reference = match.group(1)
            if reference.startswith("./"):
                continue
            _, separator, revision = reference.rpartition("@")
            if not separator or not SHA_REF.fullmatch(revision):
                errors.append(f"{workflow.relative_to(ROOT)}:{line_number}: unpinned action {reference}")
    return errors


def dockerfile_errors() -> list[str]:
    errors: list[str] = []
    for dockerfile in sorted(ROOT.glob("*/Dockerfile")):
        for line_number, line in enumerate(dockerfile.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("FROM ") and not DIGEST_REF.search(line):
                errors.append(f"{dockerfile.relative_to(ROOT)}:{line_number}: base image is not digest-pinned")
    return errors


def main() -> int:
    errors = workflow_errors() + dockerfile_errors()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("CI actions and Dockerfile base images are pinned to immutable revisions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
