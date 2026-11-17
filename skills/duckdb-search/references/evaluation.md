# Retrieval evaluation reference

Read this when a ranked search needs a number, not a demo: nDCG@k, recall@k, MRR, or latency from a labeled query set.

The SQL below was run on DuckDB 2.0.0. It assumes two tables:

- `qrels(qid, doc_id, rel)`: graded or binary judgments. A row with `rel > 0` is relevant.
- `runs(qid, doc_id, score)`: one row per retrieved document and arm.

## Contract

```text
Inputs:      qrels with at least one relevant doc per scored query; runs with one score per query/doc
Outputs:     per-query nDCG@k, recall@k, MRR; average across queries
Invariant:   rank with a deterministic tie-break; compute per query, then average
Failure:     pooling rows before averaging weights queries by result count, not equally
Proof:       a hand-computed fixture matches the three metrics
```

## Metrics

Set `k` once in `params`. The `, doc_id` tie-break makes the ranking deterministic.

```sql
WITH params AS (SELECT 10 AS k),
ranked AS (
    SELECT qid, doc_id,
           row_number() OVER (PARTITION BY qid ORDER BY score DESC, doc_id) AS rn
    FROM runs
),
judged AS (
    SELECT r.qid, r.doc_id, r.rn, coalesce(q.rel, 0) AS rel
    FROM ranked r
    CROSS JOIN params p
    LEFT JOIN qrels q USING (qid, doc_id)
    WHERE r.rn <= p.k
),
dcg AS (
    SELECT qid, sum((POWER(2, rel) - 1) / LOG2(rn + 1)) AS dcg
    FROM judged
    GROUP BY qid
),
ideal AS (
    SELECT qid, sum((POWER(2, rel) - 1) / LOG2(rn + 1)) AS idcg
    FROM (
        SELECT qid, rel,
               row_number() OVER (PARTITION BY qid ORDER BY rel DESC, doc_id) AS rn
        FROM qrels
        WHERE rel > 0
    ) t
    CROSS JOIN params p
    WHERE rn <= p.k
    GROUP BY qid
),
relcount AS (
    SELECT qid, count(*) AS n_rel
    FROM qrels
    WHERE rel > 0
    GROUP BY qid
),
retrieved AS (
    SELECT qid,
           count(*) FILTER (WHERE rel > 0) AS hits,
           min(CASE WHEN rel > 0 THEN rn END) AS first_rel_rank
    FROM judged
    GROUP BY qid
)
SELECT d.qid,
       d.dcg / nullif(i.idcg, 0) AS ndcg_at_k,
       coalesce(r.hits, 0)::DOUBLE / rc.n_rel AS recall_at_k,
       coalesce(1.0 / r.first_rel_rank, 0) AS mrr
FROM dcg d
JOIN ideal i USING (qid)
JOIN relcount rc USING (qid)
LEFT JOIN retrieved r USING (qid)
ORDER BY d.qid;
```

Average across queries with `avg(ndcg_at_k)`, `avg(recall_at_k)`, and `avg(mrr)`. Do not average the pooled rows.

- Binary relevance: set `rel` to `0` or `1`.
- Graded relevance: use the editorial grades. `POWER(2, rel) - 1` gives the usual gain.
- `recall_at_k` divides by every relevant document. A query with more than `k` relevant documents cannot reach `1.0`.
- `mrr` uses the first relevant rank, so it only needs the first hit.
- A query with no relevant documents has no `ideal` row and drops out of the join. Report how many queries were scored.

A fixture with two queries, three results each, and a hand-computed check:

```text
qrels: (1,1,2), (1,2,1), (2,10,1)
runs:  (1,3,9), (1,1,5), (1,2,1), (2,11,9), (2,10,1)
k=3
query 1: nDCG 0.6590018, recall 1.0, MRR 0.5
query 2: nDCG 0.6309298, recall 1.0, MRR 0.5
```

## Latency

Measure the query you will ship, including planning. `EXPLAIN ANALYZE (FORMAT JSON)` returns `query.total_time` in seconds:

```sql
EXPLAIN ANALYZE (FORMAT JSON)
SELECT ...;
```

Read `query.total_time`, not the sum of operator timings. Operator timings are exclusive and can exceed wall time on a parallel query. See `duckdb-profile` for the full metric list.

In Python, `execute()` returns one row with two columns. Parse the second:

```python
row = con.execute("EXPLAIN ANALYZE (FORMAT JSON) SELECT ...").fetchone()
metrics = json.loads(row[1])
latency_ms = metrics["query"]["total_time"] * 1000
```

The CLI prints the JSON object directly. Report p50 and p95, not only the mean:

```sql
CREATE TABLE timings (run_id VARCHAR, qid INTEGER, latency_ms DOUBLE);

SELECT quantile_cont(latency_ms, [0.5, 0.95, 0.99]) AS p50_p95_p99
FROM timings;
```

Keep the index build time, bytes per vector, candidate limit, and `hnsw_ef_search` beside quality. A result row without that configuration is not citable.

## Traps

| Trap | Effect | Correct move |
| --- | --- | --- |
| Merge all `runs` rows, then average | Long result lists dominate | Compute per `qid`, then average. |
| Rank with `ORDER BY score` only | Ties make runs non-reproducible | Add the document id as a tie-break. |
| Use `nDCG` on binary labels without saying so | Reader assumes graded judgments | State the label scale. |
| Compare raw BM25 and cosine scores | Scales are not comparable | Fuse ranks, or normalize each leg first. |
| Tune on the test split | The reported number is optimistic | Select on dev, report on test. |
| Quote one latency run | Cold cache and concurrency dominate | Report p50 and p95 across repeated runs. |

## References

- [Window functions](https://duckdb.org/docs/2.0/sql/functions/window_functions.html) documents `row_number` and frames.
- [EXPLAIN ANALYZE](https://duckdb.org/docs/2.0/guides/meta/explain_analyze.html) documents the JSON profile.
- [trec_eval](https://trec.nist.gov/trec_eval/) is the reference implementation of nDCG, recall, and MRR.
