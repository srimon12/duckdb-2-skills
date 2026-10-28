#!/usr/bin/env python3
"""Re-run the executable claims in the pack against a real DuckDB 2.0 binary."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
DUCKDB = os.environ.get("DUCKDB", "duckdb")


class ProbeError(RuntimeError):
    pass


def duckdb(sql: str, cwd: Path, args: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [DUCKDB, "-dark-mode", "-no-agent", "-json", *args, "-c", sql],
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
    decoder = json.JSONDecoder()
    pos = 0
    results: list[dict] = []
    while pos < len(text):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            break
        obj, end_pos = decoder.raw_decode(text, pos)
        if isinstance(obj, list):
            results = obj
        pos = end_pos
    return results


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


def head_status(url: str) -> int:
    try:
        # Cloudflare returns 403 for Python's default User-Agent.
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "DuckDB/2.0.0"})
        with urllib.request.urlopen(request, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except OSError:
        return 0


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
        [DUCKDB, "-dark-mode", "-no-agent", "-c",
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
        [DUCKDB, "-dark-mode", "-no-agent", "-c", "EXPLAIN (SQL) SELECT 42"],
        cwd=tmp,
        capture_output=True,
        text=True,
        timeout=120,
    )
    value = proc.stdout.strip()
    return proc.returncode == 0 and value.upper().startswith("SELECT"), value[:80]


def check_agent_mode(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-dark-mode", "-agent", "-c", "SELECT range AS i FROM range(2000)"],
        cwd=tmp,
        capture_output=True,
        text=True,
        timeout=120,
    )
    ok = "first 20 and last 20 of 2000 rows" in proc.stdout and "hash" in proc.stdout
    return ok, "truncation footer present" if ok else proc.stdout[-160:]


def check_csv_disables_agent(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-dark-mode", "-csv", "-c", "SELECT 42 AS answer"],
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


def check_async_threads(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one("SET async_threads = 16; SELECT current_setting('async_threads') AS v", tmp)
    return str(got["v"]) == "16", str(got)


def check_variant_concat_absent(tmp: Path, network: bool) -> tuple[bool, str]:
    return expect_error(
        "SELECT variant_concat([1]::VARIANT, [2]::VARIANT)",
        tmp,
        "variant_concat does not exist",
    )


def check_variant_dedup(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one(
        "SELECT count(DISTINCT v) AS n FROM (VALUES (1::VARIANT), (1::BIGINT::VARIANT), ('1'::VARIANT)) t(v)",
        tmp,
    )
    return got["n"] == 2, str(got)


def check_variant_order_hierarchy(tmp: Path, network: bool) -> tuple[bool, str]:
    res = rows(
        "SELECT typeof(v) AS t, v FROM (VALUES ({'a':1}::VARIANT), (NULL::VARIANT), (1::VARIANT), (true::VARIANT), ('z'::VARIANT), ([1]::VARIANT)) t(v) ORDER BY v",
        tmp,
    )
    ordered_values = [r["v"] for r in res]
    ok = (
        ordered_values[0] is True
        and ordered_values[1] == 1
        and ordered_values[2] == "z"
        and ordered_values[3] == [1]
        and ordered_values[4] == {"a": 1}
        and ordered_values[5] is None
    )
    return ok, str(ordered_values)


def check_json_merge_patch(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one("SELECT json_merge_patch('{\"a\": 1}', '{\"b\": 2}') AS v", tmp)
    return got["v"] == {"a": 1, "b": 2}, str(got)


def check_data_modifying_cte(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one(
        "CREATE TABLE src(id INT); INSERT INTO src VALUES (1), (2);"
        "CREATE TABLE dst(id INT);"
        "WITH deleted AS (DELETE FROM src RETURNING id) INSERT INTO dst SELECT id FROM deleted;"
        "SELECT count(*) AS n FROM dst",
        tmp,
    )
    return got["n"] == 2, str(got)


def check_secret_manager(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one(
        "CREATE TEMPORARY SECRET s_probe (TYPE S3, KEY_ID 'test_key', SECRET 'test_secret');"
        "SELECT type, provider FROM duckdb_secrets() WHERE name = 's_probe'",
        tmp,
    )
    return got == {"type": "s3", "provider": "config"}, str(got)


def check_explain_estimate(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-dark-mode", "-no-agent", "-c",
         "CREATE TABLE t AS SELECT range AS id FROM range(100000);"
         " EXPLAIN SELECT count(*) FROM t WHERE id < 10;"],
        cwd=tmp, capture_output=True, text=True, timeout=120,
    )
    ok = proc.returncode == 0 and "~" in proc.stdout and "rows" in proc.stdout
    return ok, "estimate present" if ok else proc.stdout[-120:]


def check_explain_analyze(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-dark-mode", "-no-agent", "-c",
         "CREATE TABLE t AS SELECT range AS id FROM range(100000);"
         " EXPLAIN ANALYZE SELECT count(*) FROM t WHERE id < 10;"],
        cwd=tmp, capture_output=True, text=True, timeout=120,
    )
    ok = proc.returncode == 0 and "Total Time:" in proc.stdout and "10 rows" in proc.stdout
    return ok, "actual rows and timing present" if ok else proc.stdout[-120:]


def check_explain_json(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-dark-mode", "-no-agent", "-c", "EXPLAIN (FORMAT JSON) SELECT 42 AS x;"],
        cwd=tmp, capture_output=True, text=True, timeout=120,
    )
    try:
        tree = json.loads(proc.stdout)
        ok = proc.returncode == 0 and tree[0]["name"] == "PROJECTION"
        detail = tree[0]["name"] if ok else str(tree)[:120]
    except Exception as exc:  # noqa: BLE001 - a malformed plan is the result
        ok, detail = False, f"{type(exc).__name__}: {exc}"
    return ok, detail


def check_explain_json_shape(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-no-agent", "-json", "-c",
         "CREATE TABLE t AS SELECT range AS id FROM range(1000);"
         " EXPLAIN (FORMAT JSON) SELECT count(*) FROM t WHERE id < 10;"],
        cwd=tmp, capture_output=True, text=True, timeout=120,
    )
    try:
        tree = json.loads(proc.stdout)
        node = tree[0]
        ok = (
            isinstance(tree, list)
            and node["name"] == "UNGROUPED_AGGREGATE"
            and "intermediate_rows" not in node
            and "Estimated Cardinality" in node["extra_info"]
        )
        detail = f"array root={node['name']} no actuals"
        return ok, detail if ok else str(tree)[:160]
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        return False, f"{type(exc).__name__}: {proc.stdout[:120]}"


def check_explain_analyze_json_shape(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-no-agent", "-json", "-c",
         "CREATE TABLE t AS SELECT range AS id FROM range(1000);"
         " EXPLAIN ANALYZE (FORMAT JSON) SELECT count(*) FROM t WHERE id < 10;"],
        cwd=tmp, capture_output=True, text=True, timeout=120,
    )
    try:
        profile = json.loads(proc.stdout)
        found: list[dict] = []

        def visit(node: dict) -> None:
            if node.get("type") == "TABLE_SCAN":
                found.append(node)
            for child in node.get("children") or []:
                visit(child)

        for root in profile["operator"]:
            visit(root)
        scan = found[0] if found else {}
        ok = (
            isinstance(profile, dict)
            and {"operator", "query", "io", "system"} <= set(profile)
            and scan.get("type") == "TABLE_SCAN"
            and scan.get("intermediate_rows") == 10
            and "rows_scanned" in scan
        )
        detail = f"object sections={sorted(profile)} scan_rows={scan.get('rows_scanned')}"
        return ok, detail if ok else str(profile)[:160]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        return False, f"{type(exc).__name__}: {proc.stdout[:120]}"


def check_explain_analyze_not_json(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-no-agent", "-json", "-c", "EXPLAIN ANALYZE SELECT 42 AS x;"],
        cwd=tmp, capture_output=True, text=True, timeout=120,
    )
    ok = proc.returncode == 0 and "Total Time:" in proc.stdout
    try:
        json.loads(proc.stdout)
        ok = False
    except json.JSONDecodeError:
        pass
    return ok, "text profile, not JSON" if ok else proc.stdout[:160]


def check_legacy_metrics_shape(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-no-agent", "-json", "-c",
         "SET legacy_metrics_format=true;"
         " EXPLAIN ANALYZE (FORMAT JSON) SELECT 42 AS x;"],
        cwd=tmp, capture_output=True, text=True, timeout=120,
    )
    try:
        text = proc.stdout[proc.stdout.find("{") :]
        profile = json.loads(text)
        ok = "latency" in profile and "children" in profile and "operator" not in profile
        return ok, "legacy flat shape" if ok else str(profile)[:160]
    except json.JSONDecodeError as exc:
        return False, f"{type(exc).__name__}: {proc.stdout[:120]}"


def check_profile_spill(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-no-agent", "-json", "-c",
         "SET memory_limit='100MB'; SET temp_directory='spill'; SET threads=2;"
         " EXPLAIN ANALYZE (FORMAT JSON)"
         " SELECT range i, repeat('x', 100) s FROM range(2000000) ORDER BY i DESC;"],
        cwd=tmp, capture_output=True, text=True, timeout=180,
    )
    try:
        profile = json.loads(proc.stdout)
        peak = profile["system"]["peak_temp_dir_size"]
        ok = peak > 0
        return ok, f"peak_temp_dir_size={peak}" if ok else str(profile.get("system"))
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return False, f"{type(exc).__name__}: {proc.stderr[:120]}"


def check_fts_freshness(tmp: Path, network: bool) -> tuple[bool, str]:
    db = str(tmp / "fts.duckdb")
    rows(
        "LOAD fts;"
        " CREATE TABLE docs (id INTEGER NOT NULL, body VARCHAR);"
        " INSERT INTO docs VALUES (1, 'alpha duck'), (2, 'beta cat');"
        " PRAGMA create_fts_index('docs', 'id', 'body', incremental = 1);",
        tmp,
        (db,),
    )
    rows("DELETE FROM docs WHERE id = 2; INSERT INTO docs VALUES (2, 'quokka');", tmp, (db,))
    new_term = one(
        "SELECT count(*) AS n FROM ("
        " SELECT id, fts_main_docs.match_bm25(id, 'quokka') AS score FROM docs"
        ") WHERE score IS NOT NULL",
        tmp,
        (db,),
    )
    old_term = one(
        "SELECT count(*) AS n FROM ("
        " SELECT id, fts_main_docs.match_bm25(id, 'cat') AS score FROM docs"
        ") WHERE score IS NOT NULL",
        tmp,
        (db,),
    )
    ok = new_term["n"] == 1 and old_term["n"] == 0
    return ok, f"new={new_term['n']} old={old_term['n']}"


def check_vss_hnsw(tmp: Path, network: bool) -> tuple[bool, str]:
    db = str(tmp / "vss.duckdb")
    rows(
        "LOAD vss;"
        " SET hnsw_enable_experimental_persistence = true;"
        " CREATE TABLE items (id INTEGER, emb FLOAT[3]);"
        " INSERT INTO items VALUES (1, [1, 0, 0]), (2, [0, 1, 0]);"
        " CREATE INDEX items_hnsw ON items USING HNSW (emb) WITH (metric = 'cosine');",
        tmp,
        (db,),
    )
    indexed = duckdb(
        "LOAD vss; EXPLAIN SELECT id FROM items"
        " ORDER BY array_cosine_distance(emb, [1, 0, 0]::FLOAT[3]) LIMIT 1;",
        tmp,
        (db,),
    )
    similarity = duckdb(
        "LOAD vss; EXPLAIN SELECT id FROM items"
        " ORDER BY array_cosine_similarity(emb, [1, 0, 0]::FLOAT[3]) DESC LIMIT 1;",
        tmp,
        (db,),
    )
    ok = (
        indexed.returncode == 0
        and "Hnsw Index Scan" in indexed.stdout
        and similarity.returncode == 0
        and "Hnsw Index Scan" not in similarity.stdout
    )
    return ok, "cosine index scan; similarity falls back"


def check_parquet_pagination(tmp: Path, network: bool) -> tuple[bool, str]:
    rows(
        "COPY (SELECT range AS id FROM range(30000) ORDER BY id)"
        " TO 'pages.parquet' (FORMAT parquet, ROW_GROUP_SIZE 5000);",
        tmp,
    )
    seen: list[int] = []
    for start in range(0, 30000, 1000):
        page = rows(
            "SET threads = 4; SET preserve_insertion_order = false;"
            " SELECT id FROM read_parquet('pages.parquet', file_row_number = true)"
            f" WHERE file_row_number >= {start} AND file_row_number < {start + 1000}"
            " ORDER BY id;",
            tmp,
        )
        seen.extend(row["id"] for row in page)
    ok = seen == list(range(30000))
    return ok, f"rows={len(seen)} distinct={len(set(seen))}"


def check_2_0_parser_traps(tmp: Path, network: bool) -> tuple[bool, str]:
    ok, detail = expect_error(
        "CREATE TABLE t AS SELECT NULL AS x; INSERT INTO t VALUES (1);",
        tmp,
        "Unimplemented type for cast",
    )
    if not ok:
        return ok, detail
    got = one(
        "SELECT typeof(X'4142') AS x, typeof(B'1010') AS b,"
        " 2 * 3! AS product, (2 * 3)! AS parenthesized;",
        tmp,
    )
    expected = {"x": "BLOB", "b": "BIT", "product": "12", "parenthesized": "720"}
    return got == expected, str(got)


def check_plan_lint_selftest(tmp: Path, network: bool) -> tuple[bool, str]:
    script = ROOT / "skills/duckdb-profile/scripts/plan_lint.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--self-test"],
        cwd=tmp, capture_output=True, text=True, timeout=300,
        env={**os.environ, "DUCKDB": DUCKDB},
    )
    ok = (
        proc.returncode == 0
        and "PASS cross join" in proc.stdout
        and "PASS write guard" in proc.stdout
    )
    return ok, "write guard and 4 plan cases pass" if ok else (proc.stderr or proc.stdout)[-160:]


def check_explain_analyze_dml(tmp: Path, network: bool) -> tuple[bool, str]:
    db = tmp / "dml.duckdb"
    db.unlink(missing_ok=True)
    proc = duckdb(
        f"ATTACH '{db}' AS d; CREATE TABLE d.t(id INT);"
        " EXPLAIN ANALYZE INSERT INTO d.t SELECT range FROM range(3);",
        tmp,
    )
    got = one(f"ATTACH '{db}' AS d; SELECT count(*) AS n FROM d.t", tmp)
    ok = proc.returncode == 0 and got["n"] == 3
    return ok, f"inserted {got['n']} rows during ANALYZE"


def check_parquet_row_groups(tmp: Path, network: bool) -> tuple[bool, str]:
    rows(
        "COPY (SELECT range AS id FROM range(100000) ORDER BY id)"
        " TO 'rg.parquet' (FORMAT parquet, ROW_GROUP_SIZE 10000)",
        tmp,
    )
    proc = subprocess.run(
        [DUCKDB, "-dark-mode", "-no-agent", "-c",
         "EXPLAIN ANALYZE SELECT count(*) FROM 'rg.parquet' WHERE id = 99999;"],
        cwd=tmp, capture_output=True, text=True, timeout=120,
    )
    ok = "Row Groups Scanned: 1 / 10" in proc.stdout
    return ok, "1 of 10 row groups" if ok else proc.stdout[-160:]


def check_parquet_metadata_dup(tmp: Path, network: bool) -> tuple[bool, str]:
    rows(
        "COPY (SELECT i AS a, i + 1 AS b, i + 2 AS c FROM range(10) t(i))"
        " TO 'meta.parquet' (FORMAT parquet)",
        tmp,
    )
    got = one(
        "SELECT (SELECT CAST(sum(num_rows) AS BIGINT) FROM parquet_file_metadata('meta.parquet')) AS file_rows,"
        " (SELECT CAST(sum(row_group_num_rows) AS BIGINT) FROM parquet_metadata('meta.parquet')) AS chunk_rows",
        tmp,
    )
    ok = got["file_rows"] == 10 and got["chunk_rows"] == 30
    return ok, str(got)


def check_parquet_schema_drift(tmp: Path, network: bool) -> tuple[bool, str]:
    drift = tmp / "drift"
    drift.mkdir(exist_ok=True)
    rows("COPY (SELECT 1 AS a, 2 AS b) TO 'drift/a.parquet' (FORMAT parquet)", tmp)
    rows("COPY (SELECT 1 AS a, 3 AS c) TO 'drift/b.parquet' (FORMAT parquet)", tmp)
    ok, detail = expect_error("FROM read_parquet('drift/*.parquet')", tmp, "schema mismatch")
    if not ok:
        return ok, detail
    got = rows(
        "FROM read_parquet('drift/*.parquet', union_by_name = true)"
        " ORDER BY b NULLS LAST, c NULLS LAST",
        tmp,
    )
    ok = len(got) == 2 and got[0]["b"] == 2 and got[0]["c"] is None and got[1]["b"] is None
    return ok, str(got)


def check_partitioned_copy(tmp: Path, network: bool) -> tuple[bool, str]:
    rows(
        "COPY (SELECT i AS id, 2024 AS y, i % 3 + 1 AS m FROM range(9) t(i))"
        " TO 'parts' (FORMAT parquet, PARTITION_BY (y, m), OVERWRITE,"
        " FILENAME_PATTERN 'part_{i}', RETURN_FILES)",
        tmp,
    )
    got = one(
        "SELECT (SELECT count(*) FROM read_parquet('parts/*/*/*.parquet')) AS n,"
        " (SELECT CAST(sum(num_rows) AS BIGINT) FROM parquet_file_metadata('parts/*/*/*.parquet')) AS meta",
        tmp,
    )
    ok = got["n"] == 9 and got["meta"] == 9
    return ok, str(got)


def check_copy_overwrite_guard(tmp: Path, network: bool) -> tuple[bool, str]:
    rows(
        "COPY (SELECT 1 AS id, 2024 AS y, 1 AS m UNION ALL SELECT 2, 2024, 2)"
        " TO 'guard' (FORMAT parquet, PARTITION_BY (y, m))",
        tmp,
    )
    return expect_error(
        "COPY (SELECT 1 AS id, 2024 AS y, 1 AS m)"
        " TO 'guard' (FORMAT parquet, PARTITION_BY (y, m))",
        tmp,
        "not empty",
    )


def check_overwrite_or_ignore_stale(tmp: Path, network: bool) -> tuple[bool, str]:
    rows(
        "COPY (SELECT 1 AS id, 2024 AS y, 1 AS m UNION ALL SELECT 2, 2024, 2)"
        " TO 'stale' (FORMAT parquet, PARTITION_BY (y, m))",
        tmp,
    )
    rows(
        "COPY (SELECT 1 AS id, 2024 AS y, 1 AS m)"
        " TO 'stale' (FORMAT parquet, PARTITION_BY (y, m), OVERWRITE_OR_IGNORE)",
        tmp,
    )
    got = one("SELECT count(*) AS n FROM read_parquet('stale/*/*/*.parquet')", tmp)
    ok = got["n"] == 2
    return ok, f"stale partition remains, {got['n']} rows"


def check_overwrite_removes_stale(tmp: Path, network: bool) -> tuple[bool, str]:
    rows(
        "COPY (SELECT 1 AS id, 2024 AS y, 1 AS m UNION ALL SELECT 2, 2024, 2)"
        " TO 'clear' (FORMAT parquet, PARTITION_BY (y, m))",
        tmp,
    )
    rows(
        "COPY (SELECT 1 AS id, 2024 AS y, 1 AS m)"
        " TO 'clear' (FORMAT parquet, PARTITION_BY (y, m), OVERWRITE)",
        tmp,
    )
    got = one("SELECT count(*) AS n FROM read_parquet('clear/*/*/*.parquet')", tmp)
    ok = got["n"] == 1
    return ok, f"old partition removed, {got['n']} rows"


def check_rejects_one_row_per_error(tmp: Path, network: bool) -> tuple[bool, str]:
    (tmp / "bad.csv").write_text("id,amount,name\n1,10,A\nx,y,B\n3,30,C\n", encoding="utf-8")
    got = one(
        "CREATE TABLE typed AS FROM read_csv('bad.csv',"
        " columns = {'id': 'BIGINT', 'amount': 'DECIMAL(18,2)', 'name': 'VARCHAR'},"
        " store_rejects = true, rejects_table = 'rejects');"
        " SELECT count(*) AS errors, count(DISTINCT file_id || ':' || line) AS lines FROM rejects",
        tmp,
    )
    ok = got["errors"] == 2 and got["lines"] == 1
    return ok, str(got)


def check_row_group_min(tmp: Path, network: bool) -> tuple[bool, str]:
    rows(
        "COPY (SELECT range AS i FROM range(10000)) TO 'rgmin.parquet'"
        " (FORMAT parquet, ROW_GROUP_SIZE 1000)",
        tmp,
    )
    got = one(
        "SELECT max(row_group_num_rows) AS n FROM parquet_metadata('rgmin.parquet') WHERE column_id = 0",
        tmp,
    )
    return got["n"] == 2048, f"full row group {got['n']}"


def check_json_ignore_errors_null(tmp: Path, network: bool) -> tuple[bool, str]:
    (tmp / "bad.jsonl").write_text(
        '{"id":1,"name":"a"}\nnot json\n{"id":3,"name":"c"}\n', encoding="utf-8"
    )
    got = rows(
        "FROM read_json('bad.jsonl', format = 'newline_delimited', ignore_errors = true)",
        tmp,
    )
    ok = len(got) == 3 and got[1]["id"] is None and got[1]["name"] is None
    return ok, str(got)


def check_ui_extension(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run([DUCKDB, "-help"], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0 or "-ui" not in proc.stdout:
        return False, "ui flag missing from -help"
    if not network:
        return True, "skipped (network)"

    home = tmp / "ui-home"
    home.mkdir(exist_ok=True)
    log = tmp / "ui.log"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    ok = False
    detail = "ui server did not start"
    with log.open("w", encoding="utf-8") as out:
        ui = subprocess.Popen(
            [DUCKDB, "-no-agent"],
            cwd=tmp,
            env=env,
            stdin=subprocess.PIPE,
            stdout=out,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            assert ui.stdin is not None
            try:
                ui.stdin.write(
                    f"INSTALL ui;\nLOAD ui;\nSET ui_local_port = {port};\nCALL start_ui_server();\n"
                )
                ui.stdin.flush()
            except OSError:
                pass
            for _ in range(120):
                if ui.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen(f"http://localhost:{port}/", timeout=2) as resp:
                        body = resp.read(256)
                        ok = resp.status == 200 and b"<!DOCTYPE html>" in body
                        detail = "ui server started"
                        break
                except OSError:
                    time.sleep(1)
        finally:
            ui.terminate()
            try:
                ui.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ui.kill()
                ui.wait()
    if not ok:
        return False, log.read_text(encoding="utf-8")[-200:].strip() or detail

    version = one("PRAGMA version", tmp)["library_version"]
    platform = one("PRAGMA platform", tmp)["platform"]
    base = f"https://extensions.duckdb.org/{version}"
    status = head_status(f"{base}/{platform}/ui.duckdb_extension.gz")
    if status != 200:
        return False, f"{platform} ui URL returned {status}"
    for unsupported in ("osx_amd64", "windows_arm64"):
        status = head_status(f"{base}/{unsupported}/ui.duckdb_extension.gz")
        if status != 404:
            return False, f"{unsupported} ui URL returned {status}; update the docs"
    return True, "ui server started; osx_amd64 and windows_arm64 missing"


def check_cli_cmd_after_c(tmp: Path, network: bool) -> tuple[bool, str]:
    proc = subprocess.run(
        [DUCKDB, "-no-agent", "-json", "-c", "SELECT 1 AS a", "-cmd", "SELECT 2 AS b"],
        cwd=tmp, capture_output=True, text=True, timeout=120,
    )
    ok_c = proc.returncode == 0 and '"a":1' in proc.stdout and '"b":2' in proc.stdout
    (tmp / "cmd.sql").write_text("SELECT 3 AS c;\n", encoding="utf-8")
    proc_f = subprocess.run(
        [DUCKDB, "-no-agent", "-json", "-f", "cmd.sql", "-cmd", "SELECT 4 AS d"],
        cwd=tmp, capture_output=True, text=True, timeout=120,
    )
    ok_f = proc_f.returncode == 0 and '"c":3' in proc_f.stdout and '"d":4' in proc_f.stdout
    return ok_c and ok_f, "trailing -cmd runs after -c and -f" if ok_c and ok_f else (proc.stderr + proc_f.stderr)[:160]


def check_agent_footer_thresholds(tmp: Path, network: bool) -> tuple[bool, str]:
    def footer(n: int) -> str:
        proc = subprocess.run(
            [DUCKDB, "-agent", "-c", f"SELECT * FROM range({n})"],
            cwd=tmp, capture_output=True, text=True, timeout=120,
        )
        return proc.stdout

    zero, five, ten = footer(0), footer(5), footer(10)
    ok = "0 rows" in zero and "hash" in zero and "hash" not in five and "10 rows" in ten and "hash" in ten
    return ok, "0/10 hash, 5 no hash" if ok else f"0={zero[-60:]!r} 5={five[-60:]!r} 10={ten[-60:]!r}"


def check_friendly_from_first(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one(
        "CREATE TABLE events(kind VARCHAR, user_id INTEGER);"
        " INSERT INTO events VALUES ('click', 1), ('view', 2);"
        " FROM events SELECT user_id, count(*) AS clicks"
        " WHERE kind = 'click' GROUP BY ALL ORDER BY clicks DESC",
        tmp,
    )
    return got == {"user_id": 1, "clicks": 1}, str(got)


def check_friendly_unpack_struct(tmp: Path, network: bool) -> tuple[bool, str]:
    struct_rows = rows("SELECT s.* FROM (SELECT {'x': 1, 'y': 2} AS s)", tmp)
    unpacked = one(
        "CREATE TABLE flags(flag_a BOOLEAN, flag_b BOOLEAN);"
        " INSERT INTO flags VALUES (true, false);"
        " SELECT greatest(UNPACK(COLUMNS('^flag_'))) AS any_flag FROM flags",
        tmp,
    )
    ok = struct_rows == [{"x": 1, "y": 2}] and unpacked == {"any_flag": True}
    return ok, f"struct={struct_rows} unpack={unpacked}"


def check_trigger_mixing(tmp: Path, network: bool) -> tuple[bool, str]:
    return expect_error(
        "CREATE TABLE t(id INTEGER); CREATE TABLE a(id INTEGER);"
        " CREATE TRIGGER s AFTER INSERT ON t FOR EACH STATEMENT INSERT INTO a VALUES (1);"
        " CREATE TRIGGER r AFTER INSERT ON t FOR EACH ROW INSERT INTO a VALUES (NEW.id)",
        tmp,
        "Mixing FOR EACH STATEMENT and FOR EACH ROW",
    )


def check_trigger_temp_catalog(tmp: Path, network: bool) -> tuple[bool, str]:
    return expect_error(
        "CREATE TEMP TABLE t(id INTEGER); CREATE TABLE a(id INTEGER);"
        " CREATE TRIGGER x AFTER INSERT ON t FOR EACH ROW INSERT INTO a VALUES (NEW.id)",
        tmp,
        "different catalog",
    )


def check_legacy_parser_nearest(tmp: Path, network: bool) -> tuple[bool, str]:
    ok, detail = expect_error(
        "SET enable_legacy_parser = true; CREATE TABLE p(id INTEGER, e DOUBLE[3]);"
        " CREATE TABLE q(id INTEGER, e DOUBLE[3]);"
        " SELECT * FROM q NEAREST 1 BY SIMILARITY array_cosine_similarity(q.e, p.e)",
        tmp,
        "syntax error",
    )
    if not ok:
        return ok, detail
    got = rows(
        "SET enable_legacy_parser = true; CREATE TABLE p(id INTEGER, e DOUBLE[3]);"
        " CREATE TABLE q(id INTEGER, e DOUBLE[3]);"
        " INSERT INTO p VALUES (1, [1,0,0]); INSERT INTO q VALUES (10, [1,0,0]);"
        " SELECT q.id AS qid, p.id AS pid FROM q INNER JOIN p NEAREST 1 BY SIMILARITY"
        " array_cosine_similarity(q.e, p.e)",
        tmp,
    )
    return len(got) == 1 and got[0]["qid"] == 10 and got[0]["pid"] == 1, str(got)


def check_read_duckdb_multi_table(tmp: Path, network: bool) -> tuple[bool, str]:
    rows(
        "ATTACH 'multi.duckdb' AS m; CREATE TABLE m.a AS SELECT 1 AS x;"
        " CREATE TABLE m.b AS SELECT 2 AS y",
        tmp,
    )
    ok, detail = expect_error("SELECT * FROM read_duckdb('multi.duckdb')", tmp, "multiple tables")
    if not ok:
        return ok, detail
    got = one("SELECT x FROM read_duckdb('multi.duckdb', table_name = 'a')", tmp)
    return got["x"] == 1, str(got)


def check_copy_unrelated_target(tmp: Path, network: bool) -> tuple[bool, str]:
    rows("ATTACH 'mig_src.duckdb' AS s; CREATE TABLE s.t AS SELECT 1 AS x", tmp)
    rows("ATTACH 'mig_dst.duckdb' AS d; CREATE TABLE d.other AS SELECT 9 AS z", tmp)
    got = one(
        "ATTACH 'mig_src.duckdb' AS s (READ_ONLY); ATTACH 'mig_dst.duckdb' AS d;"
        " COPY FROM DATABASE s TO d;"
        " SELECT (SELECT count(*) FROM d.other) AS other, (SELECT count(*) FROM d.t) AS t",
        tmp,
    )
    return got == {"other": 1, "t": 1}, str(got)


def check_import_unrelated_target(tmp: Path, network: bool) -> tuple[bool, str]:
    rows("CREATE TABLE t AS SELECT 1 AS x; EXPORT DATABASE 'exp'", tmp)
    rows("ATTACH 'imp.duckdb' AS i; CREATE TABLE i.other AS SELECT 9 AS z", tmp)
    got = one(
        "ATTACH 'imp.duckdb' AS i; USE i; IMPORT DATABASE 'exp';"
        " SELECT (SELECT count(*) FROM other) AS other, (SELECT count(*) FROM t) AS t",
        tmp,
    )
    return got == {"other": 1, "t": 1}, str(got)


def check_ingest_reject_invariant(tmp: Path, network: bool) -> tuple[bool, str]:
    (tmp / "inv.csv").write_text("a,b\n1,2\nBAD,3\n4,5\n", encoding="utf-8")
    got = one(
        "CREATE TABLE typed AS FROM read_csv('inv.csv',"
        " columns = {'a': 'INTEGER', 'b': 'INTEGER'},"
        " store_rejects = true, rejects_table = 'rejects');"
        " SELECT (SELECT count(*) FROM typed) AS typed,"
        " (SELECT count(DISTINCT file_id || ':' || line) FROM rejects) AS rejected_lines",
        tmp,
    )
    ok = got["typed"] == 2 and got["rejected_lines"] == 1 and got["typed"] + got["rejected_lines"] == 3
    return ok, str(got)


def check_storage_pin_14(tmp: Path, network: bool) -> tuple[bool, str]:
    got = one(
        "ATTACH 'pinned14.duckdb' AS d;"
        " SELECT tags['storage_version'] AS v FROM duckdb_databases() WHERE database_name = 'd'",
        tmp,
        ("-storage-version", "v1.4.0"),
    )["v"]
    return got.startswith("v1.4.0"), got


def check_python_connection_config(tmp: Path, network: bool) -> tuple[bool, str]:
    try:
        import duckdb  # type: ignore
    except Exception:
        return True, "skipped (duckdb Python package not importable)"
    if not getattr(duckdb, "__version__", "").startswith("2."):
        return True, f"skipped (duckdb {getattr(duckdb, '__version__', '?')})"
    db = tmp / "py-connection.duckdb"
    db.unlink(missing_ok=True)
    first = duckdb.connect(str(db))
    try:
        first.execute("CREATE TABLE t(x INTEGER)")
        second = duckdb.connect(str(db))
        try:
            second.execute("INSERT INTO t VALUES (1)")
        finally:
            second.close()
        try:
            third = duckdb.connect(str(db), read_only=True)
        except Exception as exc:  # noqa: BLE001 - the message is the assertion
            ok = "different configuration" in str(exc)
            return ok, f"read-only rejected: {str(exc)[:100]}" if ok else str(exc)[:160]
        third.close()
        return False, "read-only connection opened alongside a writer"
    finally:
        first.close()


CHECKS = [
    Check("version is 2.0", check_version),
    Check("lambda syntax", check_lambda),
    Check("lambda arrow rejected", check_lambda_arrow_rejected),
    Check("$variable", check_variables),
    Check("integer division by zero", check_division),
    Check("nested schema USE rejected", check_nested_schema),
    Check("default storage version", check_storage_default),
    Check("pinned storage version", check_storage_pinned),
    Check("pinned 1.4 storage version", check_storage_pin_14),
    Check("VARIANT functions and 1-based index", check_variant),
    Check("VARIANT index 0 rejected", check_variant_index_base),
    Check("VARIANT out-of-range returns NULL", check_variant_out_of_range),
    Check("variant_comparator returns BLOB", check_variant_comparator),
    Check("variant_concat absent", check_variant_concat_absent),
    Check("VARIANT distinct across types", check_variant_dedup),
    Check("VARIANT order hierarchy", check_variant_order_hierarchy),
    Check("regex ~ is partial", check_regex_partial),
    Check("decimal_division exact", check_decimal_division),
    Check("SECURE VIEW", check_secure_view),
    Check("R-tree index scan", check_rtree),
    Check("read_parquet schema rename", check_parquet_schema),
    Check("checkpoint_on_detach enum", check_checkpoint_on_detach),
    Check("row trigger", check_trigger_row),
    Check("BEFORE row trigger rejected", check_trigger_before_row),
    Check("trigger levels cannot mix", check_trigger_mixing),
    Check("temp trigger body stays in temp catalog", check_trigger_temp_catalog),
    Check("sqlite_master absent", check_sqlite_master),
    Check("read_duckdb", check_read_duckdb),
    Check("read_duckdb multi-table", check_read_duckdb_multi_table),
    Check("COPY FROM DATABASE", check_copy_database),
    Check("COPY to unrelated target", check_copy_unrelated_target),
    Check("IMPORT into unrelated target", check_import_unrelated_target),
    Check("NEAREST join", check_nearest),
    Check("legacy parser NEAREST forms", check_legacy_parser_nearest),
    Check("GROUP BY UNNEST", check_group_by_unnest),
    Check("MERGE INTO", check_merge),
    Check("EXPLAIN (SQL)", check_explain_sql),
    Check("EXPLAIN shows estimates", check_explain_estimate),
    Check("EXPLAIN ANALYZE shows actuals", check_explain_analyze),
    Check("EXPLAIN (FORMAT JSON)", check_explain_json),
    Check("EXPLAIN (FORMAT JSON) has no actuals", check_explain_json_shape),
    Check("EXPLAIN ANALYZE (FORMAT JSON) shape", check_explain_analyze_json_shape),
    Check("EXPLAIN ANALYZE ignores -json", check_explain_analyze_not_json),
    Check("legacy metrics flat shape", check_legacy_metrics_shape),
    Check("profile reports spill", check_profile_spill),
    Check("plan linter self-test", check_plan_lint_selftest),
    Check("FTS incremental freshness", check_fts_freshness),
    Check("VSS HNSW metric match", check_vss_hnsw),
    Check("Parquet stable pagination", check_parquet_pagination),
    Check("2.0 parser traps", check_2_0_parser_traps),
    Check("EXPLAIN ANALYZE executes DML", check_explain_analyze_dml),
    Check("Parquet row-group pruning", check_parquet_row_groups),
    Check("Parquet metadata row duplication", check_parquet_metadata_dup),
    Check("Parquet schema drift", check_parquet_schema_drift),
    Check("partitioned COPY round trip", check_partitioned_copy),
    Check("COPY overwrite guard", check_copy_overwrite_guard),
    Check("OVERWRITE_OR_IGNORE leaves stale partitions", check_overwrite_or_ignore_stale),
    Check("OVERWRITE removes stale partitions", check_overwrite_removes_stale),
    Check("CSV rejects one row per error", check_rejects_one_row_per_error),
    Check("ingest reject invariant", check_ingest_reject_invariant),
    Check("Parquet row group minimum", check_row_group_min),
    Check("JSON ignore_errors nulls a row", check_json_ignore_errors_null),
    Check("agent mode truncation footer", check_agent_mode),
    Check("agent footer thresholds", check_agent_footer_thresholds),
    Check("friendly FROM-first example", check_friendly_from_first),
    Check("friendly UNPACK and struct expansion", check_friendly_unpack_struct),
    Check("-csv disables agent mode", check_csv_disables_agent),
    Check("trailing -cmd runs", check_cli_cmd_after_c),
    Check("ui extension installs and serves", check_ui_extension),
    Check("async_threads setting", check_async_threads),
    Check("json_merge_patch", check_json_merge_patch),
    Check("data-modifying CTE with RETURNING", check_data_modifying_cte),
    Check("temporary secret creation", check_secret_manager),
    Check("Python connection configuration", check_python_connection_config),
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
    skips = 0
    try:
        for check in CHECKS:
            try:
                ok, detail = check.fn(tmp, args.network)
            except Exception as exc:  # noqa: BLE001 - a probe failure is data
                ok, detail = False, f"{type(exc).__name__}: {exc}"
            if ok and detail.lower().startswith("skipped"):
                status = "SKIP"
                skips += 1
            elif ok:
                status = "PASS"
            else:
                status = "FAIL"
                failures += 1
            print(f"{status} {check.name}: {detail}")
            lines.append(f"- **{status}** {check.name}: `{detail}`")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total = len(CHECKS)
    summary = f"{total - failures - skips}/{total} passed"
    if skips:
        summary += f", {skips} skipped"
    if failures:
        summary += f", {failures} failed"
    lines.append("")
    lines.append(summary)
    report = "\n".join(lines) + "\n"
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(report, encoding="utf-8")
        print(f"\nwrote {args.write}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
