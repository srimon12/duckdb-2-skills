#!/usr/bin/env python3
"""Re-run the executable claims in the pack against a real DuckDB 2.0 binary."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
DUCKDB = os.environ.get("DUCKDB", "duckdb")


class ProbeError(RuntimeError):
    pass


def duckdb(sql: str, cwd: Path, args: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [DUCKDB, "-no-agent", "-json", *args, "-c", sql],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )


def rows(sql: str, cwd: Path, args: tuple[str, ...] = ()) -> list[dict]:
    proc = duckdb(sql, cwd, args)
    if proc.returncode != 0:
        raise ProbeError(proc.stderr.strip().splitlines()[0] if proc.stderr.strip() else "query failed")
    text = proc.stdout.strip()
    if not text:
        return []
    return json.loads(text)


def one(sql: str, cwd: Path, args: tuple[str, ...] = ()) -> dict:
    result = rows(sql, cwd, args)
    if len(result) != 1:
        raise ProbeError(f"expected one row, got {len(result)}")
    return result[0]


def expect_error(sql: str, cwd: Path, needle: str, args: tuple[str, ...] = ()) -> tuple[bool, str]:
    proc = duckdb(sql, cwd, args)
    if proc.returncode == 0:
        return False, "query succeeded, expected an error"
    if needle.lower() not in proc.stderr.lower():
        return False, f"error did not contain {needle!r}: {proc.stderr.strip()[:160]}"
    return True, "rejected as documented"


@dataclass
class Check:
    name: str
    fn: Callable[[Path, bool], tuple[bool, str]]


def check_version(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one("SELECT version() AS v", tmp)["v"]
    return got.startswith("v2.0"), got


def check_lambda(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one("SELECT list_transform([1,2,3], lambda x: x + 1) AS v", tmp)["v"]
    return got == [2, 3, 4], str(got)


def check_lambda_arrow_rejected(tmp: Path, network: bool) -> tuple[bool, str]:
    return expect_error("SELECT list_transform([1], x -> x + 1)", tmp, "Deprecated lambda arrow")


def check_variables(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one("SET VARIABLE x = 7; SELECT $x AS a, getvariable('x') AS b", tmp)
    return got == {"a": 7, "b": 7}, str(got)


def check_division(tmp: Path, network: bool) -> tuple[bool, str]:
    ok, detail = expect_error("SELECT 1 // 0", tmp, "Division by zero")
    if not ok:
        return ok, detail
    got = one("SELECT TRY(1 // 0) AS a, 1 / 0 AS b", tmp)
    return got["a"] is None and got["b"] == float("inf"), str(got)


def check_nested_schema(tmp: Path, network: bool) -> tuple[bool, str]:
    ok, detail = expect_error(
        "CREATE SCHEMA s; CREATE SCHEMA s.e; USE s.e", tmp, "nested schema"
    )
    if not ok:
        return ok, detail
    got = one(
        "CREATE SCHEMA s; CREATE SCHEMA s.e;"
        " SELECT count(*) AS n FROM duckdb_schemas() WHERE schema_name = 'e' AND parent_schema = 's'",
        tmp,
    )
    return got["n"] == 1, "USE rejected; nested schema is visible through parent_schema"


def check_storage_default(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one(
        "ATTACH 'default.duckdb' AS d; SELECT tags['storage_version'] AS v FROM duckdb_databases() WHERE database_name = 'd'",
        tmp,
    )["v"]
    return got.startswith("v2.0.0"), got


def check_storage_pinned(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one(
        "ATTACH 'pinned.duckdb' AS d; SELECT tags['storage_version'] AS v FROM duckdb_databases() WHERE database_name = 'd'",
        tmp,
        ("-storage-version", "v1.5.6"),
    )["v"]
    return got.startswith("v1.5.0"), got


def check_variant(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one(
        "SELECT variant_typeof(42::VARIANT) AS t, variant_type({'a': 1}::VARIANT) AS c, variant_extract([10,20]::VARIANT, 1) AS i",
        tmp,
    )
    ok = got["t"] == "INT32" and got["c"] == "OBJECT" and got["i"] == 10
    return ok, str(got)


def check_variant_index_base(tmp: Path, network: bool) -> tuple[bool, str]:
    return expect_error("SELECT variant_extract([10,20]::VARIANT, 0)", tmp, "1-based")


def check_variant_out_of_range(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one("SELECT variant_extract([10,20]::VARIANT, 4) AS v", tmp)
    return got["v"] is None, str(got)


def check_variant_comparator(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one("SELECT typeof(variant_comparator({'a': 1}::VARIANT)) AS t", tmp)
    return got["t"] == "BLOB", str(got)


def check_regex_partial(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one("SELECT 'abc' ~ 'b' AS partial, current_setting('regex_match_operator_semantics') AS sem", tmp)
    return got["partial"] is True and got["sem"] == "partial", str(got)


def check_decimal_division(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one("SELECT decimal_division(10.00, 4.00) AS v", tmp)
    return str(got["v"]).startswith("2.5"), str(got)


def check_secure_view(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one("CREATE TABLE t(a INT); INSERT INTO t VALUES (1); CREATE SECURE VIEW v AS SELECT * FROM t; SELECT a FROM v", tmp)
    return got["a"] == 1, str(got)


def check_rtree(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-no-agent", "-c",
         "LOAD spatial; CREATE TABLE t AS SELECT point::GEOMETRY AS geom"
         " FROM st_generatepoints({min_x:0,min_y:0,max_x:100,max_y:100}::BOX_2D, 1000, 42);"
         " CREATE INDEX i ON t USING RTREE (geom);"
         " EXPLAIN SELECT count(*) FROM t WHERE ST_Within(geom, ST_MakeEnvelope(45,45,65,65));"],
        cwd=tmp, capture_output=True, text=True, timeout=120,
    )
    return proc.returncode == 0 and "Rtree Index Scan" in proc.stdout, "Rtree Index Scan" if "Rtree Index Scan" in proc.stdout else proc.stderr[:120]


def check_parquet_schema(tmp: Path, network: bool) -> tuple[bool, str]:
    rows("COPY (SELECT 1 AS a) TO 's.parquet' (FORMAT parquet)", tmp)
    got = one(
        "SELECT * FROM read_parquet('s.parquet', schema = MAP {'a': {name: 'renamed', type: 'BIGINT', default_value: NULL}})",
        tmp,
    )
    return got.get("renamed") == 1, str(got)


def check_checkpoint_on_detach(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one("SET checkpoint_on_detach = 'ENABLED'; SELECT current_setting('checkpoint_on_detach') AS v", tmp)
    return got["v"] == "ENABLED", str(got)


def check_trigger_row(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one(
        "CREATE TABLE t(id INT); CREATE TABLE log(id INT);"
        "CREATE TRIGGER tr AFTER INSERT ON t FOR EACH ROW INSERT INTO log VALUES (NEW.id);"
        "INSERT INTO t VALUES (7); SELECT count(*) AS n FROM log WHERE id = 7",
        tmp,
    )
    return got["n"] == 1, str(got)


def check_trigger_before_row(tmp: Path, network: bool) -> tuple[bool, str]:
    return expect_error(
        "CREATE TABLE t(id INT); CREATE TRIGGER tr BEFORE INSERT ON t FOR EACH ROW INSERT INTO t VALUES (NEW.id)",
        tmp,
        "BEFORE FOR EACH ROW",
    )


def check_sqlite_master(tmp: Path, network: bool) -> tuple[bool, str]:
    return expect_error("SELECT sqlite_master('x')", tmp, "does not exist")


def check_read_duckdb(tmp: Path, network: bool) -> tuple[bool, str]:
    rows("ATTACH 'src.duckdb' AS s; CREATE TABLE s.t AS SELECT 42 AS a", tmp)
    got = one("SELECT a FROM read_duckdb('src.duckdb')", tmp)
    return got["a"] == 42, str(got)


def check_copy_database(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one(
        "ATTACH 'a.duckdb' AS a; CREATE TABLE a.t AS SELECT 1 AS x;"
        "ATTACH 'b.duckdb' AS b; COPY FROM DATABASE a TO b; SELECT x FROM b.t",
        tmp,
    )
    return got["x"] == 1, str(got)


def check_nearest(tmp: Path, network: bool) -> tuple[bool, str]:
    got = rows(
        "SELECT q.id, t.id FROM (VALUES (1, [1.0,0.0]::DOUBLE[2])) q(id,e)"
        " INNER JOIN (VALUES (10,[1.0,0.0]::DOUBLE[2]),(11,[0.0,1.0]::DOUBLE[2]),(12,[0.9,0.1]::DOUBLE[2])) t(id,e)"
        " NEAREST 2 BY SIMILARITY array_cosine_similarity(q.e,t.e)",
        tmp,
    )
    ids = sorted(r["id"] for r in got)
    return len(ids) == 2 and set(ids) == {10, 12}, str(got)


def check_group_by_unnest(tmp: Path, network: bool) -> tuple[bool, str]:
    got = rows(
        "SELECT unnest(tags) AS tag, count(*) AS n FROM (VALUES (['a','b']),(['b','c']),(['b'])) t(tags)"
        " GROUP BY unnest(tags) ORDER BY tag",
        tmp,
    )
    return got == [{"tag": "a", "n": 1}, {"tag": "b", "n": 3}, {"tag": "c", "n": 1}], str(got)


def check_merge(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one(
        "CREATE TABLE t(id INT PRIMARY KEY, v INT); INSERT INTO t VALUES (1,10);"
        "MERGE INTO t USING (SELECT 1 AS id, 20 AS v) s ON t.id = s.id"
        " WHEN MATCHED THEN UPDATE SET v = s.v; SELECT v FROM t",
        tmp,
    )
    return got["v"] == 20, str(got)


def check_explain_sql(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-no-agent", "-c", "EXPLAIN (SQL) SELECT 42"],
        cwd=tmp,
        capture_output=True,
        text=True,
        timeout=120,
    )
    value = proc.stdout.strip()
    return proc.returncode == 0 and value.upper().startswith("SELECT"), value[:80]


def check_agent_mode(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-agent", "-c", "SELECT range AS i FROM range(2000)"],
        cwd=tmp,
        capture_output=True,
        text=True,
        timeout=120,
    )
    ok = "first 20 and last 20 of 2000 rows" in proc.stdout and "hash" in proc.stdout
    return ok, "truncation footer present" if ok else proc.stdout[-160:]


def check_csv_disables_agent(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-csv", "-c", "SELECT 42 AS answer"],
        cwd=tmp,
        capture_output=True,
        text=True,
        timeout=120,
    )
    ok = "agent mode" not in proc.stderr.lower() and proc.stdout.startswith("answer")
    return ok, "plain CSV" if ok else proc.stderr[:160]


def check_docs_index(tmp: Path, network: bool) -> tuple[bool, str]:
    if not network:
        return True, "skipped (network)"
    cache = tmp / "docs.duckdb"
    proc = duckdb(
        "INSTALL httpfs; LOAD httpfs; INSTALL fts; LOAD fts;"
        f"ATTACH 'https://duckdb.org/data/docs-search.duckdb' AS remote (READ_ONLY);"
        f"ATTACH '{cache}' AS local; COPY FROM DATABASE remote TO local;",
        tmp,
    )
    if proc.returncode != 0:
        return False, proc.stderr.strip().splitlines()[0]
    got = rows(
        "SELECT version, count(*) AS n FROM docs_chunks GROUP BY version ORDER BY version",
        tmp,
        ("-readonly", str(cache)),
    )
    versions = {r["version"] for r in got}
    ok = "2.0" in versions and "lts" not in versions and "current" not in versions
    return ok, str(got)


CHECKS = [
    Check("version is 2.0", check_version),
    Check("lambda syntax", check_lambda),
    Check("lambda arrow rejected", check_lambda_arrow_rejected),
    Check("$variable", check_variables),
    Check("integer division by zero", check_division),
    Check("nested schema USE rejected", check_nested_schema),
    Check("default storage version", check_storage_default),
    Check("pinned storage version", check_storage_pinned),
    Check("VARIANT functions and 1-based index", check_variant),
    Check("VARIANT index 0 rejected", check_variant_index_base),
    Check("VARIANT out-of-range returns NULL", check_variant_out_of_range),
    Check("variant_comparator returns BLOB", check_variant_comparator),
    Check("regex ~ is partial", check_regex_partial),
    Check("decimal_division exact", check_decimal_division),
    Check("SECURE VIEW", check_secure_view),
    Check("R-tree index scan", check_rtree),
    Check("read_parquet schema rename", check_parquet_schema),
    Check("checkpoint_on_detach enum", check_checkpoint_on_detach),
    Check("row trigger", check_trigger_row),
    Check("BEFORE row trigger rejected", check_trigger_before_row),
    Check("sqlite_master absent", check_sqlite_master),
    Check("read_duckdb", check_read_duckdb),
    Check("COPY FROM DATABASE", check_copy_database),
    Check("NEAREST join", check_nearest),
    Check("GROUP BY UNNEST", check_group_by_unnest),
    Check("MERGE INTO", check_merge),
    Check("EXPLAIN (SQL)", check_explain_sql),
    Check("agent mode truncation footer", check_agent_mode),
    Check("-csv disables agent mode", check_csv_disables_agent),
    Check("docs index versions", check_docs_index),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", action="store_true", help="run checks that download extensions or indexes")
    parser.add_argument("--write", type=Path, help="write the report to this path")
    args = parser.parse_args()

    probe = subprocess.run([DUCKDB, "--version"], capture_output=True, text=True)
    if probe.returncode != 0 or "v2.0" not in probe.stdout:
        print(f"need a DuckDB 2.0 binary, got: {probe.stdout.strip() or probe.stderr.strip()}", file=sys.stderr)
        return 2

    tmp = Path(tempfile.mkdtemp(prefix="duckdb-probe-"))
    lines = [f"# Probe results", "", f"Binary: {probe.stdout.strip()}", ""]
    failures = 0
    try:
        for check in CHECKS:
            try:
                ok, detail = check.fn(tmp, args.network)
            except Exception as exc:  # noqa: BLE001 - a probe failure is data
                ok, detail = False, f"{type(exc).__name__}: {exc}"
            status = "PASS" if ok else "FAIL"
            if not ok:
                failures += 1
            print(f"{status} {check.name}: {detail}")
            lines.append(f"- **{status}** {check.name}: `{detail}`")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    lines.append("")
    lines.append(f"{len(CHECKS) - failures}/{len(CHECKS)} passed")
    report = "\n".join(lines) + "\n"
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(report, encoding="utf-8")
        print(f"\nwrote {args.write}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
