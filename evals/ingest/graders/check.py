#!/usr/bin/env python3
"""Check the file-to-Parquet case without reading the candidate's process."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

DUCKDB = os.environ.get("DUCKDB", "duckdb")


def query(case_dir: Path, sql: str) -> list[dict]:
    proc = subprocess.run(
        [DUCKDB, "-dark-mode", "-no-agent", "-json", "-c", sql],
        cwd=case_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "duckdb failed")
    text = proc.stdout.strip()
    return json.loads(text) if text else []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--truth", type=Path, required=True)
    args = parser.parse_args()
    case_dir = args.case_dir.resolve()
    truth = json.loads(args.truth.read_text(encoding="utf-8"))

    failures: list[str] = []
    passes: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            passes.append(name)
        else:
            failures.append(f"{name}: {detail}")

    files = sorted(case_dir.glob("out/*/*/*.parquet"))
    check("partition files exist", bool(files), f"found {len(files)} under out/*/*/*.parquet")
    if not files:
        return report(passes, failures)

    partition_keys: set[tuple[int, int]] = set()
    path_errors = []
    for path in files:
        parts = path.relative_to(case_dir).parts
        if len(parts) != 4 or parts[0] != "out" or not parts[1].startswith("year=") or not parts[2].startswith("month="):
            path_errors.append(str(path))
            continue
        partition_keys.add((int(parts[1][5:]), int(parts[2][6:])))
    expected_keys = {tuple(int(value) for value in key.split("-")) for key in truth["months"]}
    check("Hive path shape", not path_errors and partition_keys == expected_keys, f"{path_errors[:2]} keys={sorted(partition_keys)}")

    source = "read_parquet('out/*/*/*.parquet', hive_partitioning = true)"
    stats = query(
        case_dir,
        f"SELECT count(*) AS n, count(DISTINCT order_id) AS ids, "
        f"CAST(sum(amount) AS VARCHAR) AS amount_sum, "
        f"count(*) FILTER (WHERE order_id IS NULL OR ordered_at IS NULL "
        f"OR amount IS NULL OR payload IS NULL) AS nulls FROM {source}",
    )[0]
    check("kept row count", stats["n"] == truth["valid"], f"{stats['n']} != {truth['valid']}")
    check("distinct order ids", stats["ids"] == truth["valid"], f"{stats['ids']} != {truth['valid']}")
    check("required values not null", stats["nulls"] == 0, f"{stats['nulls']} null rows")
    check(
        "amount total",
        Decimal(stats["amount_sum"]) == Decimal(truth["valid_amount_sum"]),
        f"{stats['amount_sum']} != {truth['valid_amount_sum']}",
    )

    columns = {row["column_name"]: row["column_type"] for row in query(case_dir, f"DESCRIBE FROM {source}")}
    check("order_id type", columns.get("order_id") in {"BIGINT", "INTEGER", "UBIGINT"}, str(columns.get("order_id")))
    check("ordered_at type", columns.get("ordered_at") == "DATE", str(columns.get("ordered_at")))
    check("amount type", (columns.get("amount") or "").startswith("DECIMAL"), str(columns.get("amount")))
    check("payload type", columns.get("payload") == "JSON", str(columns.get("payload")))
    check("customer type", columns.get("customer") == "VARCHAR", str(columns.get("customer")))
    if columns.get("customer") == "VARCHAR":
        customer_nulls = query(
            case_dir,
            f"SELECT count(*) FILTER (WHERE customer IS NULL) AS n FROM {source}",
        )[0]["n"]
        check(
            "optional customer nulls",
            customer_nulls == truth["valid_customer_nulls"],
            f"{customer_nulls} != {truth['valid_customer_nulls']}",
        )

    months = {
        f"{row['y']:04d}-{row['m']:02d}": row["n"]
        for row in query(
            case_dir,
            f'SELECT "year" AS y, "month" AS m, count(*) AS n '
            f"FROM {source} GROUP BY 1, 2 ORDER BY 1, 2",
        )
    }
    check("month partitions", months == truth["months"], f"{months} != {truth['months']}")

    id_rows = query(case_dir, f"SELECT order_id FROM {source} ORDER BY order_id")
    id_hash = hashlib.sha256(",".join(str(row["order_id"]) for row in id_rows).encode()).hexdigest()
    check("valid id set", id_hash == truth["valid_ids_sha256"], f"{id_hash[:12]} != {truth['valid_ids_sha256'][:12]}")

    meta = query(
        case_dir,
        "SELECT CAST(sum(num_rows) AS BIGINT) AS n FROM parquet_file_metadata('out/*/*/*.parquet')",
    )[0]
    check("parquet footer rows", meta["n"] == truth["valid"], f"{meta['n']} != {truth['valid']}")

    quarantine = case_dir / "quarantine.parquet"
    q_n = 0
    check("quarantine exists", quarantine.exists(), "missing quarantine.parquet")
    if quarantine.exists():
        qstats = query(
            case_dir,
            "SELECT count(*) AS n, count(DISTINCT order_id) AS ids, "
            "count(*) FILTER (WHERE reason IS NULL OR trim(reason) = '') AS empty_reason "
            "FROM 'quarantine.parquet'",
        )[0]
        q_n = qstats["n"]
        check("quarantine row count", qstats["n"] == truth["quarantine"], f"{qstats['n']} != {truth['quarantine']}")
        check("quarantine distinct ids", qstats["ids"] == truth["quarantine"], f"{qstats['ids']} != {truth['quarantine']}")
        check("quarantine reasons", qstats["empty_reason"] == 0, f"{qstats['empty_reason']} empty")

        bad_ids = [int(key) for key in truth["bad"]]
        bad_list = "[" + ",".join(str(value) for value in bad_ids) + "]"
        qrows = query(case_dir, f"SELECT order_id, reason FROM 'quarantine.parquet'")
        seen = {row["order_id"]: (row["reason"] or "").lower() for row in qrows}
        check("all bad ids quarantined", set(seen) == set(bad_ids), f"{len(seen)} of {len(bad_ids)}")
        missing_reasons = []
        for order_id, flags in truth["bad"].items():
            reason = seen.get(int(order_id), "")
            if flags["date"] and "date" not in reason:
                missing_reasons.append(order_id)
            if flags["amount"] and "amount" not in reason:
                missing_reasons.append(order_id)
            if flags["json"] and "json" not in reason and "payload" not in reason:
                missing_reasons.append(order_id)
        check("reasons name the failure", not missing_reasons, f"missing on {len(missing_reasons)} rows")

        bad_in_output = query(
            case_dir,
            f"SELECT count(*) AS n FROM {source} WHERE order_id IN (SELECT unnest({bad_list}))",
        )[0]["n"]
        check("bad rows not in output", bad_in_output == 0, f"{bad_in_output} leaked")

    proof = case_dir / "proof.txt"
    check("proof file exists", proof.exists(), "missing proof.txt")
    if proof.exists():
        proof_text = proof.read_text(encoding="utf-8").replace(",", "")
        missing = [
            str(value)
            for value in (truth["total"], truth["valid"], truth["quarantine"])
            if str(value) not in proof_text
        ]
        check("proof carries the counts", not missing, f"missing {missing}")

    check(
        "row accounting",
        stats["n"] + q_n == truth["total"],
        f"{stats['n']} + {q_n} != {truth['total']}",
    )
    return report(passes, failures)


def report(passes: list[str], failures: list[str]) -> int:
    for name in passes:
        print(f"PASS {name}")
    for name in failures:
        print(f"FAIL {name}")
    print(f"\n{len(passes)} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - a failed check is data
        print(f"FAIL harness: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
