#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")" && pwd)
case_dir=$(mktemp -d "${TMPDIR:-/tmp}/duckdb-ingest.XXXXXX")
truth_file="${case_dir}.truth.json"
trap 'rm -rf "$case_dir" "$truth_file"' EXIT

python3 "$root/make_fixture.py" "$case_dir" --truth "$truth_file" >/dev/null
(
  cd "$case_dir"
  "${DUCKDB:-duckdb}" -dark-mode -no-agent -f "$root/solution.sql"
  "${DUCKDB:-duckdb}" -dark-mode -no-agent -f "$root/proof.sql"
)
python3 "$root/graders/check.py" "$case_dir" --truth "$truth_file"
