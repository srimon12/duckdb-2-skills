#!/usr/bin/env python3
"""Fetch the pinned DuckDB and DuckLake manuals as Markdown."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "research" / "sources"

REPOS = {
    "duckdb-2.0": {
        "repo": "duckdb/duckdb-web",
        "ref": "37408677c0753c0b3607f8b77540df7f3096be95",
        "prefix": "docs/2.0/",
    },
    "ducklake-stable": {
        "repo": "duckdb/ducklake-web",
        "ref": "1b74f10e93a3905e247c12f30b8882ca683db8f4",
        "prefix": "docs/stable/",
    },
}


def tree(repo: str, ref: str) -> list[str]:
    url = f"https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1"
    with urllib.request.urlopen(url, timeout=60) as response:
        data = json.load(response)
    return [item["path"] for item in data["tree"] if item["type"] == "blob"]


def fetch(repo: str, ref: str, path: str, dest: Path) -> tuple[str, str]:
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"
    target = dest / path
    if target.exists() and target.stat().st_size:
        return path, "cached"
    target.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                target.write_bytes(response.read())
            return path, "ok"
        except Exception as exc:  # noqa: BLE001 - report the last failure
            last = str(exc)
    return path, f"error: {last}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, default=SOURCES)
    parser.add_argument("--only", choices=REPOS, action="append")
    args = parser.parse_args()

    for name, spec in REPOS.items():
        if args.only and name not in args.only:
            continue
        dest = args.dest / name
        paths = [
            path
            for path in tree(spec["repo"], spec["ref"])
            if path.startswith(spec["prefix"]) and path.endswith(".md")
        ]
        if not paths:
            print(f"{name}: no markdown under {spec['prefix']}")
            return 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda p: fetch(spec["repo"], spec["ref"], p, dest), paths))
        failures = [path for path, status in results if status.startswith("error")]
        print(f"{name}: {len(paths)} files, {len(failures)} failures, {spec['ref']}")
        for path in failures[:10]:
            print(f"  {path}")
        (dest / "COMMIT").write_text(spec["ref"] + "\n", encoding="utf-8")
        if failures:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
