# Ingest task case

This is the one task case for the file-to-Parquet workflow. It tests the work, not the trigger table.

## Run the reference

```bash
bash evals/ingest/run_reference.sh
```

The reference writes `out/`, `quarantine.parquet`, and `proof.txt`, then the grader checks 25 conditions. It needs DuckDB 2.0 on `PATH` or in `DUCKDB`.

A first candidate smoke run quarantined blank optional customers and failed 8 checks. The skill now names nullable columns in the ingest contract and the prompt allows an empty customer. A final maintainer smoke run passed 25 of 25, and the reference passes the same set.

## Run a candidate

Create two directories. Generate the fixture in one, and put only `orders.csv` and the brief in the other. Do not copy `truth.json`, `solution.sql`, or this README.

```bash
fixture_dir=$(mktemp -d)
case_dir=$(mktemp -d)
python3 evals/ingest/make_fixture.py "$fixture_dir" --truth "$fixture_dir/truth.json"
cp "$fixture_dir/orders.csv" "$case_dir/orders.csv"
cp evals/ingest/prompt.md "$case_dir/BRIEF.md"
# Candidate works in case_dir.
python3 evals/ingest/graders/check.py "$case_dir" --truth "$fixture_dir/truth.json"
```

Keep `truth.json` outside the candidate directory. The fixture is deterministic.

## Pass bar

The candidate must keep 55,913 rows, quarantine 4,087 rows, preserve the declared types, use `year=` and `month=` Hive directories, keep 579 optional customers as `NULL`, write a proof file, and make the Parquet footer count match the clean input. A row with two bad fields is one quarantine row with both reasons.
