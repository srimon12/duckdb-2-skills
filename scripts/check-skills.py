#!/usr/bin/env python3
"""Structural checks for the skill pack. Run from the repo root."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
BACKTICK_SKILL_RE = re.compile(r"`(duckdb(?:-[a-z0-9]+)*)`")
# Hard failures are reserved for text that is wrong in a command, with no
# legitimate reason to appear. Anything a skill may need to explain as removed
# is a warning, so a deprecation note does not fail the build.
STALE = [
    ("duckdb-skills:", "Claude-only slash command; use the skill name"),
]
STALE_IF_UNEXPLAINED = [
    ("sqlite_master(", "sqlite_master(path) is not a 2.0 function; ATTACH TYPE sqlite", ("not", "removed", "absent")),
    ("read_any(", "the read_any macro was not carried into this pack", ("not", "macro", "old")),
    ("-csv -c", "prefer -agent for model-read output; -csv disables agent mode", ("agent", "disables", "not")),
]
SOFT = [
    ("x ->", "single-arrow lambda is disabled; write lambda x: ..."),
    ("postgres://", "2.0 CONNECT uses postgres:dbname=... host=..."),
    ("version = 'lts'", "the 2.0 index has no lts version"),
    ("version = 'current'", "the 2.0 index has no current version"),
    ("categories.primary", "Overture removed categories.primary; use taxonomy.primary"),
    ("2026-03-18", "stale Overture release; resolve from the STAC catalog"),
]
REQUIRED_HEADINGS = ["## Verify", "## References"]
MAX_SKILL_LINES = 200
MAX_REFERENCE_LINES = 450


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 5 :]
    fields: dict[str, str] = {}
    key = None
    for line in raw.splitlines():
        if re.match(r"^[A-Za-z_-]+:", line):
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
        elif key and line.startswith((" ", "\t")):
            fields[key] = (fields[key] + " " + line.strip()).strip()
    for k, v in list(fields.items()):
        if v in {">", "|", ">-", "|-"}:
            fields[k] = ""
    return fields, body


def check_skill(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    text = path.read_text(encoding="utf-8")
    fields, body = split_frontmatter(text)

    name = fields.get("name", "")
    description = fields.get("description", "")
    if not name:
        errors.append("frontmatter: missing name")
    elif name != path.parent.name:
        errors.append(f"frontmatter: name {name!r} does not match directory {path.parent.name!r}")
    elif not NAME_RE.match(name):
        errors.append(f"frontmatter: name {name!r} is not lower-kebab-case")
    if not description:
        errors.append("frontmatter: missing description")
    else:
        if not 40 <= len(description) <= 1024:
            errors.append(f"frontmatter: description is {len(description)} chars, expected 40-1024")
        if "use when" not in description.lower() and "use for" not in description.lower():
            warnings.append("frontmatter: description has no 'Use when' trigger clause")

    if not re.search(r"^# \S", body, re.MULTILINE):
        errors.append("body: no level-1 title")

    for heading in REQUIRED_HEADINGS:
        label = heading.removeprefix("## ")
        if not re.search(rf"^##\s+(?:\d+\.\s+)?{re.escape(label)}\s*$", body, re.MULTILINE):
            errors.append(f"body: missing a '## {label}' section")

    lines = body.count("\n") + 1
    if lines > MAX_SKILL_LINES:
        errors.append(f"body: {lines} lines, budget is {MAX_SKILL_LINES}")

    for pattern, why in STALE:
        for lineno, line in enumerate(body.splitlines(), 1):
            if pattern in line:
                errors.append(f"stale text line {lineno}: {pattern!r} ({why})")
    for pattern, why, allowed in STALE_IF_UNEXPLAINED:
        for lineno, line in enumerate(body.splitlines(), 1):
            if pattern in line and not any(word in line.lower() for word in allowed):
                errors.append(f"stale text line {lineno}: {pattern!r} ({why})")
    for pattern, why in SOFT:
        for lineno, line in enumerate(body.splitlines(), 1):
            if pattern in line:
                warnings.append(f"review line {lineno}: {pattern!r} ({why})")

    for target in LINK_RE.findall(body):
        target = target.split("#", 1)[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            errors.append(f"link: {target!r} does not resolve from {path.parent.name}/")

    known = {p.name for p in SKILLS.iterdir() if p.is_dir()}
    for token in set(BACKTICK_SKILL_RE.findall(body)):
        if token.startswith("duckdb-") and token not in known:
            warnings.append(f"cross-skill: `{token}` does not match a skill directory")

    refs_dir = path.parent / "references"
    if refs_dir.exists():
        for ref in sorted(refs_dir.glob("*.md")):
            ref_lines = ref.read_text(encoding="utf-8").count("\n") + 1
            if ref_lines > MAX_REFERENCE_LINES:
                errors.append(f"{ref.name}: {ref_lines} lines, budget is {MAX_REFERENCE_LINES}")
            if not body.count(ref.name):
                warnings.append(f"{ref.name}: not linked from SKILL.md")

    if not re.search(r"https://(duckdb\.org|ducklake\.select|docs\.overturemaps\.org)", body):
        errors.append("references: no official documentation URL")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args()

    skill_dirs = sorted(p for p in SKILLS.iterdir() if p.is_dir())
    if not skill_dirs:
        print("no skills found", file=sys.stderr)
        return 2

    total_errors = 0
    total_warnings = 0
    for path in skill_dirs:
        skill_file = path / "SKILL.md"
        if not skill_file.exists():
            print(f"FAIL {path.name}: missing SKILL.md")
            total_errors += 1
            continue
        errors, warnings = check_skill(skill_file)
        status = "FAIL" if errors else ("WARN" if warnings else "PASS")
        print(f"{status} {path.name}")
        for item in errors:
            print(f"  error: {item}")
        for item in warnings:
            print(f"  warn:  {item}")
        total_errors += len(errors)
        total_warnings += len(warnings)

    print(f"\n{len(skill_dirs)} skills, {total_errors} errors, {total_warnings} warnings")
    if total_errors or (args.strict and total_warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
