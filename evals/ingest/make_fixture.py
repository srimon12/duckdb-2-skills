#!/usr/bin/env python3
"""Create a messy orders export and the expected counts for the ingest case."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

TOTAL = 60_000
SEED = 20261022
START = date(2024, 1, 1)
DAYS = 182
NAMES = ["Ada", "Grace", "Lin", "Ken", "Mira", "Noah", "Ruth", "Sam"]
TIERS = ["gold", "silver", "bronze"]


def sample_indices(rng: random.Random, rate: float) -> set[int]:
    return set(rng.sample(range(TOTAL), int(TOTAL * rate)))


def make_row(rng: random.Random, index: int, bad_date: set[int], bad_amount: set[int], bad_json: set[int]) -> dict:
    order_id = 100_000 + index
    if index in bad_date:
        ordered_at = rng.choice(["2024-13-40", "99/99/2024", "not-a-date"])
    else:
        value = START + timedelta(days=rng.randrange(DAYS))
        ordered_at = value.isoformat() if rng.random() < 0.6 else value.strftime("%d/%m/%Y")

    customer = "" if rng.random() < 0.01 else rng.choice(NAMES)

    if index in bad_amount:
        amount = "not-a-number"
    else:
        value = Decimal(rng.randrange(500, 200_000)) / 100
        style = rng.randrange(4)
        if style == 0:
            amount = f"{value:.2f}"
        elif style == 1:
            amount = f"${value:,.2f}"
        elif style == 2:
            amount = f"€{value:.2f}"
        else:
            amount = f"{value:,.2f}"

    if index in bad_json:
        payload = f"not-json-{order_id}"
    else:
        body = {
            "customer_id": f"c{index % 5000}",
            "tier": rng.choice(TIERS),
        }
        if rng.random() < 0.2:
            body["tags"] = rng.sample(["vip", "repeat", "trial"], rng.randrange(1, 3))
        payload = json.dumps(body, separators=(",", ":"))

    return {
        "order_id": str(order_id),
        "ordered_at": ordered_at,
        "customer": customer,
        "amount": amount,
        "payload": payload,
        "_valid_date": index not in bad_date,
        "_valid_amount": index not in bad_amount,
        "_valid_json": index not in bad_json,
        "_amount_value": None if index in bad_amount else Decimal(
            amount.replace("$", "").replace("€", "").replace(",", "")
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path, help="directory for orders.csv")
    parser.add_argument("--truth", type=Path, help="write truth.json here instead of the output directory")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    rng = random.Random(SEED)
    bad_date = sample_indices(rng, 0.03)
    bad_amount = sample_indices(rng, 0.02)
    bad_json = sample_indices(rng, 0.02)
    rows = [make_row(rng, i, bad_date, bad_amount, bad_json) for i in range(TOTAL)]

    fields = ["order_id", "ordered_at", "customer", "amount", "payload"]
    with (args.output / "orders.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fields})

    bad = {}
    months = Counter()
    amount_sum = Decimal("0")
    valid = 0
    valid_ids: list[int] = []
    customer_nulls = 0
    for row in rows:
        flags = {
            "date": not row["_valid_date"],
            "amount": not row["_valid_amount"],
            "json": not row["_valid_json"],
        }
        if any(flags.values()):
            bad[row["order_id"]] = flags
            continue
        valid += 1
        valid_ids.append(int(row["order_id"]))
        if row["customer"] == "":
            customer_nulls += 1
        amount_sum += row["_amount_value"]
        parsed = row["ordered_at"]
        if "/" in parsed:
            day, month, year = parsed.split("/")
            parsed = date(int(year), int(month), int(day))
        else:
            parsed = date.fromisoformat(parsed)
        months[f"{parsed.year:04d}-{parsed.month:02d}"] += 1

    def id_hash(values: list[int]) -> str:
        return hashlib.sha256(",".join(str(value) for value in sorted(values)).encode()).hexdigest()

    truth = {
        "total": TOTAL,
        "valid": valid,
        "quarantine": len(bad),
        "bad": bad,
        "months": dict(sorted(months.items())),
        "valid_amount_sum": f"{amount_sum:.2f}",
        "valid_customer_nulls": customer_nulls,
        "valid_ids_sha256": id_hash(valid_ids),
    }
    truth_path = args.truth or (args.output / "truth.json")
    truth_path.parent.mkdir(parents=True, exist_ok=True)
    truth_path.write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: truth[key] for key in ("total", "valid", "quarantine", "months")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
