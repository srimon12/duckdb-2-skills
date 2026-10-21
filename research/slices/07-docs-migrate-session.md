# Slice: docs search, migration, session state

Status: complete
Scope: The two hosted docs-search indexes and the cache/query workflow; DuckDB 2.0 storage versions, conversion, and migration order; native-file attach/session state, WAL, concurrency, and catalog introspection. Audits `duckdb-docs`, `duckdb-migrate` (including `references/checklist.md`), and `duckdb-session`.
Sources: `research/sources/duckdb-2.0/{operations_manual/migration.md,internals/storage.md,configuration/pragmas.md,sql/statements/{attach,copy,export,checkpoint,use}.md,connect/concurrency.md,sql/meta/duckdb_table_functions.md,operations_manual/footprint_of_duckdb/*.md,operations_manual/logging/overview.md,clients/cli/agent_mode.md,clients/python/migration.md,dev/building/overview.md,extensions/overview.md,operations_manual/installing_duckdb/requirements.md}`; `https://duckdb.org/release_calendar.html`; `https://duckdb.org/2026/10/21/announcing-duckdb-200.html`; `https://duckdb.org/data/docs-search.duckdb`; `https://ducklake.select/data/docs-search.duckdb`. Binary: v2.0.0 d54cbbe3df; comparison binaries v1.5.5 d8cdaa33fd and v1.5.6 069cc9f9b5. Skills audited at 2026-10-22T20:23Z: docs `8af9a0b8`, migrate `abef6621`, checklist `574dabd6`, session `bda31305`.

## Verified facts

### 1. Docs search index

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| 1 | The DuckDB index has exactly two `version` values: `2.0` and `blog`; there is no `lts`, `current`, or `stable` row. | `SELECT version, count(*) FROM docs_chunks GROUP BY 1` on the cached file: `2.0=2695`, `blog=999`. | Probed |
| 2 | Total DuckDB chunks = 3694; `chunk_id` is unique (3694 distinct). | `count(DISTINCT chunk_id)` = 3694. | Probed |
| 3 | The DuckLake index has one `version` value, `stable`, with 198 chunks, all distinct. `stable` is the DuckLake 1.1 manual, which requires DuckDB 2.0. | `SELECT version, count(*)`: `stable=198`; `https://ducklake.select/docs/stable/` says "1.1 stable" and "DuckLake 1.1 requires DuckDB v2.0.0 or later". | Probed |
| 4 | `docs_chunks` has exactly 7 columns, all `VARCHAR`: `chunk_id`, `page_title`, `section`, `breadcrumb`, `url`, `version`, `text`. `section` may be NULL. | `DESCRIBE`/`duckdb_columns()` on both indexes. | Probed |
| 5 | The FTS index is a separate schema named `fts_main_docs_chunks`, with tables `dict`, `docs`, `fields`, `stats`, `stopwords`, `terms`. | `duckdb_tables()` on the cached file. | Probed |
| 6 | `fields` contains three indexed fields: `page_title`, `section`, `text`. The default BM25 search covers all three, not only `text`. | `SELECT * FROM fts_main_docs_chunks.fields` → `0 page_title`, `1 section`, `2 text`. | Probed |
| 7 | Hosted indexes are read-only: HTTP/S3 `ATTACH` creates a read-only connection by default (`readonly=true`); `CREATE TABLE` on it fails with `Cannot execute statement ... attached in read-only mode!`. | `ATTACH 'https://duckdb.org/data/docs-search.duckdb' AS remote; SELECT readonly...` → true. | Probed |
| 8 | A downloaded cache is an ordinary writable DuckDB file; it is queryable read-only and should be opened with `-readonly` to avoid lock conflicts. | `CREATE TABLE probe_write(x INT)` succeeded on the cache; the same query worked with `-readonly`. | Probed |
| 9 | `chunk_id` is the `match_bm25` document key. `url` is always relative: `2.0` → `/docs/2.0/...`, `blog` → `/2026/...`, DuckLake → `/docs/stable/...`. No row has an `http` URL. | `count(*) FILTER (WHERE url LIKE 'http%')` = 0 for both indexes. | Probed |
| 10 | `match_bm25` is a stored scalar macro. Its actual 2.0 signature has 10 parameters: `match_bm25(docname, query_string, fields := NULL, k := 1.2, b := 0.75, conjunctive := false, field_weights := NULL, field_b := NULL, scoring_model := 'bm25f', tie_breaker := 0.0)`. | Error candidate list from binding a wrong named argument; `duckdb_functions().macro_definition`. | Probed |
| 11 | The FTS manual page lists only six parameters (`input_id, query_string, fields, k, b, conjunctive`); it is stale for 2.0. | `core_extensions/full_text_search.md` lines 71-84 vs the macro above. | Probed |
| 12 | `stemmer`, `stopwords`, and `ignore` are **not** `match_bm25` parameters; they are `PRAGMA create_fts_index` parameters. `bm25_k1` and `bm25_b` are not valid names anywhere; use `k` and `b`. | Passing each to `match_bm25` returns `Macro match_bm25() does not support the supplied arguments`; passing `k := 1.5`, `b := 0.5` works. | Probed |
| 13 | `field_weights := {'text': 2.0}`, `field_b := {'text': 0.5}`, `scoring_model := 'best_fields'`, and `tie_breaker := 0.5` (with `best_fields`) all bind and return results. `tie_breaker` alone fails: `tie_breaker is only supported with best_fields scoring`. | One query per argument. | Probed |
| 14 | The working 2.0 query opens the cache as the main database and uses a subquery. Filtering `version='2.0'` inside the subquery limits candidates; `WHERE score IS NOT NULL` removes non-matches. | Query below returned `Variant Type / Parquet Support` at 7.50. | Probed |
| 15 | The same-SELECT alias filter fails: `SELECT ..., match_bm25(...) AS score FROM docs_chunks WHERE version='2.0' AND score IS NOT NULL` → `Binder Error: Alias ""score"" referenced - but the expression has side effects. This is not yet supported.` | Reproduced on 2.0.0. `QUALIFY score IS NOT NULL` fails identically. | Probed |
| 16 | A subquery is **not** required to order by the alias: `ORDER BY score DESC LIMIT n` in the same SELECT works. It is required only when the alias is referenced in `WHERE`/`QUALIFY`. A CTE also works. | Same query with only `ORDER BY` returned the same top 3. | Probed |
| 17 | Filtering on `score IS NOT NULL` is optional: without it, NULL scores sort last under the default `NULLS_LAST` for `DESC`, and the top rows are unchanged. | `count(*)` = 2695, `count(score)` = 69; top 3 identical with and without the filter. | Probed |
| 18 | `fts_main_docs_chunks.match_bm25` does not resolve through an attached catalog, even when qualified `alias.fts_main_docs_chunks.match_bm25`: the macro body references `fts_main_docs_chunks.terms` unqualified. `USE alias` fixes it; opening the cache as main also fixes it. | Attached `d` + `d.fts_main...` → `schema "fts_main_docs_chunks" does not exist`; `USE d` → works. | Probed |
| 19 | The query also works directly against the hosted index with `ATTACH ...; USE remote;` (no cache), taking ~4.9 s versus ~0.2 s locally. | Remote `USE remote` top result `Pragmas / Checkpointing` at 4.616. | Probed |
| 20 | Cache refresh via `COPY FROM DATABASE` works: 7.6 s, 13 MB cache, both versions and all FTS tables present. | Exact refresh block below. | Probed |

Working query (cache opened as main database, `-readonly`):

```sql
LOAD fts;
SELECT page_title, section, breadcrumb, url, version, score
FROM (
    SELECT page_title, section, breadcrumb, url, version, text,
           fts_main_docs_chunks.match_bm25(chunk_id, 'variant extract') AS score
    FROM docs_chunks
    WHERE version = '2.0'
)
WHERE score IS NOT NULL
ORDER BY score DESC
LIMIT 8;
```

### 2. Docs workflow

| # | Decision | Rule | Evidence | Confidence |
|---|---|---|---|---|
| 21 | Cache location | `$HOME/.duckdb/docs/duckdb-docs.duckdb` and `$HOME/.duckdb/docs/ducklake-docs.duckdb`; `mkdir -p "$HOME/.duckdb/docs"`. | Pack convention; upstream `duckdb-skills` uses the same path. | Probed |
| 22 | Refresh rule | Refresh when missing, when `mtime` is older than 2 days, when the expected `version` row is absent, or on a DuckDB/DuckLake release day. Keep the old cache if refresh fails and label it stale. | Cache age is only a proxy; no build timestamp inside the file. | Probed |
| 23 | Stale detection | Run `SELECT version, count(*) FROM docs_chunks GROUP BY 1` and compare with the recorded counts (`2.0=2695`, `blog=999`, `stable=198` on 2026-10-22). A missing `2.0`/`stable` row is decisive; a count change means refresh. | Counts above; verify block in `duckdb-docs`. | Probed |
| 24 | URL prefix | Prefix relative URLs: DuckDB 2.0 and blog → `https://duckdb.org`; DuckLake → `https://ducklake.select`. Never prefix twice. | All 3694 DuckDB rows and 198 DuckLake rows are relative. | Probed |
| 25 | Chunks to return | `LIMIT 8` is the pack default. Average chunk = 1781 chars; top 8 for one query = 32,591 chars (max single chunk 12,124). Read 8, quote 1-3; truncate `text` for scanning if context is tight. | `avg(length(text))`, `sum(length(text))` over top 8. | Probed |
| 26 | Answering | Lead with the answer in 1-2 sentences; then page title + absolute URL per chunk; quote only the signature or rule. Do not paste whole chunks. | `duckdb-docs` Answer section. | Documented |
| 27 | Fallback: index unreachable | Use an existing cache read-only with a stale warning. If no cache, try the remote index with `ATTACH ...; USE remote;` and the same query (works, ~5 s). If no network, say so and link `https://duckdb.org/docs/2.0/` or `https://ducklake.select/docs/stable/`. | Remote `USE remote` probe. | Probed |
| 28 | Fallback: no results | Drop the least specific term once; if `conjunctive := 1` was used, retry with `0`; remove the `version` filter to include `blog`; then stop and say no match. | `conjunctive` default is `0`, so "set 0" is a no-op unless it was 1. | Probed |
| 29 | Not to do | Do not scrape docs HTML per question; do not recite the manual; do not pass a full natural-language question to BM25; do not open the cache read-write; do not qualify the FTS macro through an attach alias. | Cache has full text + URLs; BM25 is term-based; writer locks exclude readers. | Probed |

Refresh block (verified):

```sql
INSTALL httpfs; LOAD httpfs;
INSTALL fts; LOAD fts;
ATTACH 'https://duckdb.org/data/docs-search.duckdb' AS remote (READ_ONLY);
ATTACH '/absolute/cache.tmp' AS tmp;
COPY FROM DATABASE remote TO tmp;
```

Then close every process using the cache, `mv /absolute/cache.tmp "$HOME/.duckdb/docs/duckdb-docs.duckdb"`, and reopen with `duckdb -readonly`.

### 3. Storage versions

| Storage | DuckDB line | 2.0 read/write | 1.5.6 read |
|---|---|---|---|
| 64, 65, 66 | 0.9-1.3; 64 is the default for 1.0-1.5 | yes | yes |
| 67, 68 | 1.4, 1.5 (68 is opt-in) | yes | yes |
| 69 | 2.0 default | yes | no |
| 999 | 2.0 header sentinel, not a version | n/a | 69 (1.5.6) / 999 (1.5.5) |

| # | Fact | Evidence | Confidence |
|---|---|---|---|
| 30 | A file created by 2.0 defaults to storage version 69, `tags['storage_version'] = 'v2.0.0+'`, and the first 16-byte header ends in `DUCK` + 999 (`0x3e7`). The 999 is a format sentinel, not a version to compare. | `duckdb new.db -c "CREATE TABLE..."`; `tags`; `hexdump -n 20`. | Probed |
| 31 | The tag is a compatibility floor, not the exact number. A 69 file shows `v2.0.0+`; a 68 file created by 2.0 with `-storage-version v1.5.6` shows `v1.5.0+`; a default 1.5.6 file (storage 64) shows `v1.0.0+`. | Three files, `tags` + header. | Probed |
| 32 | 1.5.6's default new file is storage 64, not 68. Version 68 is opt-in with `-storage-version v1.5.6`. | `v1.5.6 db -c "CREATE TABLE..."` → header `0x40` (64), tag `v1.0.0+`; with `-storage-version v1.5.6` → header `0x44` (68), tag `v1.5.0+`. | Probed |
| 33 | 1.5.6 can read 64-68; it refuses 69 with `IO Error: Trying to read a database file with version number 69, but we can only read versions between 64 and 68.` | 1.5.6 binary on `default.db` (69). | Probed |
| 34 | 1.5.5 reports the same 69 file as version 999: `... version number 999, but we can only read versions between 64 and 68.` | 1.5.5 binary on `default.db`. | Probed |
| 35 | 2.0 reads and writes 64-69 (all six storage versions probed by creation). Writing an existing old file keeps its version by default; a plain `INSERT` into a 64 file left it at 64 and 1.5.6 still read it. | 2.0 writes to `v156.db` (64), `old.db` (68); headers + 1.5.6 reads; `-storage-version v1.3.0` → 66. | Probed |
| 36 | Opening an old file does not upgrade it. | Same as #35: after 2.0 opened and wrote, tag/header unchanged. | Probed |
| 37 | `ATTACH existing (STORAGE_VERSION 'latest')` followed by a write **does** upgrade the file to 69. The first 16-byte header still says 68; only the database headers and `tags` show 69, and 1.5.6 then refuses it. | Copied 68 file, attached with `latest`, created one table: tag `v2.0.0+`, 1.5.6 error `file was written with a storage version greater...`. | Probed |
| 38 | `ATTACH existing (STORAGE_VERSION <lower>)` fails: `cannot initialize database with storage version 68 - which is lower than what the database itself uses (69). The storage version of an existing database cannot be lowered.` | 69 file attached with `v1.5.6`. | Probed |
| 39 | `-storage-version` applies to the CLI session's main file and to new files attached in that session, but is ignored for an existing main file. | `duckdb main.db -storage-version v1.5.6` + `ATTACH new` → both 68; an existing 69 main opened with the flag stayed 69 and wrote normally. | Probed |
| 40 | `SET storage_compatibility_version='v1.5.6'` affects subsequent `ATTACH`/creation, not the already-open main database. | `duckdb set3.db -c "SET ...; CREATE TABLE..."` → tag `v2.0.0+`; `SET ...; ATTACH set2.db; CREATE` → `v1.5.0+`. | Probed |
| 41 | `SET storage_compatibility_version` default is `latest`; `checkpoint_on_detach` default is `DEFAULT`; `max_execution_time` default is `0`; `temp_directory` default is `.tmp`. | `duckdb_settings()` values. | Probed |
| 42 | Requested storage strings map to a minimum format: `v1.0.0`→64, `v1.2.0`→65, `v1.3.0`→66, `v1.4.0`→67, `v1.5.0`/`v1.5.6`→68, `latest`→69. Tags: `v1.0.0+`, `v1.2.0+`, `v1.3.0+`, `v1.4.0+`, `v1.5.0+`, `v2.0.0+`. | Seven `-storage-version` files. | Probed |
| 43 | `COPY FROM DATABASE` copies schema, constraints, indexes, sequences, macros, and data. The target's storage version controls the output. The target may hold unrelated objects, but any same-named object aborts with `Table with name "t" already exists!`. | Copy into a 68 target → 1.5.6 reads; target with only `other` kept `other` and added `t`; target with `t` errored. Index/view/macro/sequence/constraint checks present. | Probed |
| 44 | `EXPORT DATABASE` defaults to CSV (`t.csv`), not Parquet; add `(FORMAT parquet)`. It preserves tables, views, indexes, macros, sequences, and constraints. `IMPORT DATABASE` fails if the target already contains an exported object (`already exists`); unrelated objects are not the documented blocker. | `EXPORT DATABASE 'expdefault'` → `schema.sql`, `load.sql`, `t.csv`; import round-trip checks; conflicting import error. | Probed |
| 45 | `EXPORT DATABASE` does not clear an existing directory; it overwrites same-named files and leaves unrelated files. Use an empty directory. | Exported into a dir containing `keep.txt`; `keep.txt` remained. | Probed |
| 46 | `checkpoint_on_detach` accepts `ENABLED`, `DISABLED`, `DEFAULT` (not boolean). `ENABLED`/`DEFAULT` remove the attached file's `.wal` on `DETACH`; `DISABLED` leaves it, and the next open replays it. | Python: after `DETACH` files list; reattach count = 1. | Probed |
| 47 | A native file has a `<db>.wal` while uncommitted to the data file; `CHECKPOINT` removes it, a clean exit checkpoints and removes it, a crash leaves it for replay. | After INSERT: `wal.db.wal` 276 bytes; after `CHECKPOINT`: only `wal.db`; clean close same. | Probed |
| 48 | `CHECKPOINT` fails while a transaction is running; `FORCE CHECKPOINT` waits for the checkpoint lock from 1.4 onward; `PRAGMA force_checkpoint` forces a no-change checkpoint. | `checkpoint.md`; `CHECKPOINT one`/`FORCE CHECKPOINT one` succeed. | Documented |

### 4. Migration breaks

`operations_manual/migration.md` has ten breaking-change subsections: storage format, lambda syntax, SQL parser, C API v2, ICU removal, division by zero, identifier case, S3 URL parameters, removed settings, CLI log storage. The announcement adds compiler, amalgamation, platform, and client items.

| # | Break | 2.0 behavior / replacement | Surface | Confidence |
|---|---|---|---|---|
| 49 | Storage format | New files are 69; pre-2.0 cannot read them; old files keep their version by default; override with `STORAGE_VERSION` upgrades. | Deployment + CLI | Probed |
| 50 | Lambda syntax | `x -> expr` disabled; use `lambda x: expr`; `SET lambda_syntax='enable_single_arrow'` is a bridge removed in 2.1. | SQL | Probed |
| 51 | SQL parser | PEG parser is default; `INSTALL AND LOAD legacy_parser; SET enable_legacy_parser=true;` reverts grammar only. `SET enable_legacy_parser=true` autoloads. | SQL | Probed |
| 52 | C API v2 | Ships but is not stable; extensions must rebuild; no ABI stability promise. | Deployment | Documented |
| 53 | ICU | Removed from core; `icu` extension supplies time zones/calendars/collations; official binaries ship it statically linked; custom builds must load it. | Deployment | Probed |
| 54 | Integer `//` and `%` by zero | Raise `Invalid Input Error: Division by zero...`; `TRY(expr)` returns NULL; `1 / 0` is still `inf`. `SET error_on_division_by_zero=false` restores NULL but warns that it is deprecated. | SQL | Probed |
| 55 | Identifier case | `preserve_identifier_case` is VARCHAR: `preserve_case` (default), `lowercase`, `uppercase`; `true`/`false` still map. | SQL/setting | Probed |
| 56 | S3 URL parameters | `?s3_access_key_id=...` is part of the key; use a secret; `SET s3_enable_deprecated_url_parameters=true` (after `LOAD httpfs`) is the temporary bridge. | SQL/config | Documented |
| 57 | Removed settings | `custom_profiling_settings` removed → `tracked_metrics`; `enable_http_logging`/`http_logging_output` removed → `CALL enable_logging('HTTP')`; `profiling_mode` deprecated/ignored → `SET enable_profiling`. | SQL | Probed |
| 58 | CLI log storage | CLI defaults to `shell_log_storage`, not queryable; `CALL enable_logging(storage='memory')` before `duckdb_logs`. | CLI | Probed |
| 59 | Regex `~` / `!~` | 1.5.6: full-string match (`'xERRORy' ~ 'ERROR'` = false); 2.0: substring match (true). Not listed on the migration page. Use `regexp_full_match` for old behavior. | SQL | Probed |
| 60 | Unquoted table-function arguments | `read_csv(w07.csv)` works with a deprecation warning; a path with `/` fails. `table_function_identifier_conversion='ENABLE_IMPLICIT_STRING'` restores it and is itself deprecated. | SQL | Probed |
| 61 | C++17 | Required to build 2.0; earlier required C++11. | Deployment/build | Documented |
| 62 | Amalgamation | Deprecated; custom builds should use CMake. | Deployment/build | Announced |
| 63 | `osx_amd64` | Partial support; core extensions still built, community extensions not; 2.1 drops it. Linux binaries need glibc 2.28+. | Deployment/platform | Documented |
| 64 | Python | Python 3.11+ required (3.10 pip gets 1.x); 15 API breaks (Arrow/Polars, relation fetch, expressions, transactions, Decimal, batch size, storage config). | Client/deployment | Documented |
| 65 | Extensions | Builds are tied to the DuckDB version and stored under `~/.duckdb/extensions/<duckdb_version>/<platform>/`; run `UPDATE EXTENSIONS` or `FORCE INSTALL` after upgrading, then restart. | Deployment | Documented |
| 66 | Agent mode | Auto-on when a known agent env var is set, stdout is not a terminal, and no output flag is passed; `-csv`/`-json` disable it; `-no-agent`/`DUCKDB_AGENT_MODE=0` force off. Banner and JSON errors go to stderr. | CLI | Probed |
| 67 | `max_execution_time` | New wall-clock bound in ms; default 0 = no limit; per-connection with global fallback; error `Query exceeded maximum execution time`. | SQL/session | Probed |
| 68 | `checkpoint_on_detach` | New enum setting; see #46. | SQL/session | Probed |
| 69 | Python API detail | `execute()` results no longer expose `fetch_arrow_table`/`fetch_record_batch`/`arrow`/`pl`; relation `fetchone`/`fetchmany`/`execute` gone; plain strings in expressions are values; dotted names are not split; non-string dict keys become MAP; failed statements abort transactions; `overwrite=False` raises; Arrow batch default 131072. | Client | Documented |

### 5. Migration order and support

| # | Phase | Concrete action | Gate |
|---|---|---|---|
| 70 | Inventory | `duckdb --version`; `which -a duckdb`; `SELECT version();`; `duckdb_databases()` tags/paths; `duckdb_extensions()`; `duckdb_settings()`; list every process, service, notebook, and client. | Every shared file has an owner and a binary/version. |
| 71 | Compatibility pin | If any reader stays on 1.4/1.5, create new files with `-storage-version v1.5.6` or `ATTACH ... (STORAGE_VERSION 'v1.5.6')` **at creation**. Never `ATTACH` an existing file with `latest` unless an upgrade is intended. | `tags` shows the expected floor (`v1.5.0+`), not `v2.0.0+`. |
| 72 | Backup | Stop writers, `CHECKPOINT`, copy the `.db` and any `.wal`; optionally `EXPORT DATABASE 'backup' (FORMAT parquet)`; open the backup read-only and count rows. | Restore tested, not just written. |
| 73 | Shadow copy | Run the real workload against the backup/copy with 2.0; compare row counts, aggregates, `SUMMARIZE`, plans, extensions. | Every difference explained. |
| 74 | Test | Application suite, Python 3.11+, extension loads, storage tags, views/indexes/constraints/sequences/macros, agent-mode output. | Suite passes on the shadow. |
| 75 | Cut over | Stop all old processes; upgrade binary and every extension together; verify no 1.x process remains; smoke test. | Production read/write for one full cycle. |
| 76 | Rollback | Keep the old binary and backup. If only old-format files were written, 1.x can reopen them (2.0 writes kept the version). If a 69 file was written, restore the copy or use 2.0 to `COPY FROM DATABASE` into a `STORAGE_VERSION 'v1.5.6'` target before switching back. | Restore/down-copy tested. |
| 77 | Support windows | 2.0.0 LTS 2026-10-21 → 2027-10-22; 1.4 LTS → 2026-11-17; 1.5 → 2027-03-01; 2.0.1 planned 2026-11-18, tentative. | Release calendar. |
| 78 | Waiting for patches | The guide says mission-critical workloads should "consider waiting for upcoming patch releases" and run a shadow system; 1.5 support through March 2027 makes waiting possible. | `migration.md` Before You Migrate + announcement. |
| 79 | Refuse without a backup | In-place storage conversion, `ATTACH ... (STORAGE_VERSION 'latest')` + write on an existing file, `EXPORT`/`IMPORT` over live data, `COPY FROM DATABASE` into a target with conflicting objects, deleting a `.wal`, `ATTACH OR REPLACE`, and any `DROP`/`TRUNCATE` before verification. | Agent stops and asks for a verified backup. |

### 6. Grep checklist for application SQL

| # | Pattern (GNU/BSD `grep -nE`, unless noted) | Finds | Replacement |
|---|---|---|---|
| 80 | `\b[a-z_][a-z0-9_]*[[:space:]]*->[[:space:]]*[a-z_(]` | Single-arrow lambda; JSON `->` with a quoted key is excluded, but a numeric RHS can be missed. | `lambda x: expr`; inspect every `->` hit. |
| 81 | `//[[:space:]]*0\|%[[:space:]]*0` | Literal division/modulo by zero. | `TRY(expr)`; treat `error_on_division_by_zero=false` as temporary (deprecated). |
| 82 | `s3://[^']*\?s3_` | S3 URL parameters. | A secret (`CREATE SECRET`), not a URL query string. |
| 83 | `custom_profiling_settings` | Removed setting. | `tracked_metrics`. |
| 84 | `enable_http_logging\|http_logging_output` | Removed settings. | `CALL enable_logging('HTTP')`. |
| 85 | `profiling_mode` | Deprecated/no-op. | `SET enable_profiling`. |
| 86 | `preserve_identifier_case[[:space:]]*=` | Boolean form. | `'preserve_case'` / `'lowercase'` / `'uppercase'`. |
| 87 | `lambda_syntax` | Temporary bridge. | Remove before 2.1. |
| 88 | `error_on_division_by_zero` | Works but deprecated. | `TRY(expr)`. |
| 89 | `-storage-version\|storage_compatibility_version\|STORAGE_VERSION` | Deployment/config pins. | Audit every file; creation only. |
| 90 | `EXPORT DATABASE` | Default CSV. | Add `(FORMAT parquet)` if Parquet is expected. |
| 91 | `duckdb_logs` | CLI log storage is not queryable. | `CALL enable_logging(storage='memory')` first. |
| 92 | `\.(fetch_arrow_table\|fetch_record_batch\|arrow\|pl)\(` (Python) | Methods gone from `execute()` results. | `con.sql(q).to_arrow_table()`, `.to_arrow_reader()`, `.pl()`. |
| 93 | `rel\.(fetchone\|fetchmany\|execute)\(` (Python) | Relation methods gone. | `con.execute(q)`, `rel.materialize()`, `rel.iter_rows()`. |
| 94 | `overwrite[[:space:]]*=[[:space:]]*False` (Python) | Now raises. | Omit `overwrite` or use `True`. |

### 7. Session state

| # | Fact | Evidence | Confidence |
|---|---|---|---|
| 95 | `state.sql` is a CLI init script, not a database object. `-init` executes it at startup before `-c`; it may contain SQL and dot commands (`.maxrows` tested); a parse/SQL error aborts startup with exit 1; the `-- Loading resources` banner goes to stderr, so `-json` stdout stays clean. | `duckdb -init dots.sql`, bad init, `-json` redirect. | Probed |
| 96 | `ATTACH` is not persisted. Every CLI invocation needs `-init` (or a `.duckdbrc`), otherwise the session sees only `memory`. | `duckdb -init state.sql -c "SELECT current_database()"`; without `USE`, default is `memory`. | Probed |
| 97 | `-init` is CLI-only; Python and other clients must issue `ATTACH` in code. | CLI docs; no `-init` in Python API. | Documented |
| 98 | `ATTACH IF NOT EXISTS` is keyed on the alias, not the path. Same alias + different path is a silent no-op; same path + different alias errors `Unique file handle conflict`; a missing path is created as a new 69 file. | Three probes. | Probed |
| 99 | Default alias is the file name up to the **first** dot: `a.b.c.db` → `a`, `alias.two.db` → `alias`, `alias-one.db` → `alias-one`. Aliases with `-`, spaces, or a leading digit require double quotes in SQL. | `duckdb_databases()` + `CREATE TABLE "alias-one".t`. | Probed |
| 100 | `USE db` selects the default database (schema `main`); `USE db.schema` selects both; `USE schema` selects a schema in the current database. A second attach should not change the default. | `USE one` / `USE one.main`; state file with one `USE` keeps `one` default while `two` is attached. | Probed |
| 101 | `DETACH [DATABASE] alias` releases the file lock. The default database cannot be detached: `Cannot detach database "s1" because it is the default database. Select a different database using USE...`. | `DETACH s1` and `DETACH DATABASE one`. | Probed |
| 102 | Native concurrency is **one writer OR many readers**, not both. A writer process excludes read-only processes (`Could not set lock ... Conflicting lock is held`); two read-only processes coexist. Quack or DuckLake is the multi-writer path. | Python writer + reader subprocesses; two RO processes. | Probed |
| 103 | Multiple connections inside one process can write (MVCC), but a second connection with a different configuration (e.g., `read_only=True`) fails: `Can't open a connection to same database file with a different configuration`. | Python same-process probe. | Probed |
| 104 | `con.close()` on the only connection releases the cross-process lock; locks persist while another connection/instance holds the file. `DETACH` is the explicit release. | Process A opened, closed, slept; process B read-only succeeded. | Probed |
| 105 | Temp files: `<db>.tmp/` for an on-disk database, `.tmp/` for in-memory, controlled by `temp_directory`; `max_temp_directory_size` default is 90% of free disk; clean close removes the temp dir. | `SET temp_directory='db/spill.db.tmp'`; dir present during session, gone after close. | Probed |
| 106 | `.gitignore` for a project: `*.wal`, `*.tmp/`, and the database pattern (`*.duckdb*` or `*.db`); ignore the state directory if it can contain secrets. | `footprint_of_duckdb/gitignore_for_duckdb.md`. | Documented |
| 107 | Secrets: a literal `CREATE SECRET` is plaintext in the state file; persistent secrets are unencrypted binary in `~/.duckdb/stored_secrets` (mode 600). `duckdb_secrets()` redacts `secret=` but shows `key_id=` in clear. | `secret-state.sql` grep; `duckdb_secrets()` output. | Probed |
| 108 | State-file paths: upstream `duckdb-skills` currently uses `.duckdb-skills/state.sql` or `$HOME/.duckdb-skills/<project-id>/state.sql`; `<project-id>` is the git root (or `$PWD`) with `/` → `-`. `.duckdb/state.sql` is this pack's convention, not upstream's, and collides with `$HOME/.duckdb` when the project root is `$HOME`. | Upstream `attach-db/SKILL.md` fetched; `tr '/' '-'`. | Documented |
| 109 | For a session summary, report absolute path, alias, state file path, `tags['storage_version']`, `readonly`, and table count; then per-table `DESCRIBE` and `estimated_size`. | `duckdb_databases()`/`duckdb_tables()` queries. | Probed |

### 8. Catalog introspection (actual 2.0 columns)

| Function | Actual columns (2.0) | Use in a session summary |
|---|---|---|
| `duckdb_databases()` | `database_name, database_oid, path, comment, tags, internal, type, readonly, encrypted, cipher, options` | name/path/tag/readonly/type; `options` shows requested `storage_version` |
| `duckdb_schemas()` | `oid, database_name, database_oid, schema_name, comment, tags, internal, sql, parent_schema, parent_schema_oid` | `parent_schema` for nested schemas |
| `duckdb_tables()` | `database_name, database_oid, schema_name, schema_oid, table_name, table_oid, comment, tags, internal, temporary, has_primary_key, estimated_size, column_count, index_count, check_constraint_count, sql` | table list + size/column/index counts |
| `duckdb_columns()` | `database_name, database_oid, schema_name, schema_oid, table_name, table_oid, column_name, column_index, comment, internal, column_default, is_nullable, data_type, data_type_id, character_maximum_length, numeric_precision, numeric_precision_radix, numeric_scale, tags, is_generated, generation_expression` | per-table `DESCRIBE` replacement |
| `duckdb_views()` | `database_name, database_oid, schema_name, schema_oid, view_name, view_oid, comment, tags, internal, temporary, column_count, sql, is_bound` | view names/count/SQL |
| `duckdb_indexes()` | `database_name, database_oid, schema_name, schema_oid, index_name, index_oid, table_name, table_oid, comment, tags, is_unique, is_primary, expressions, sql` | secondary indexes only; PK/UNIQUE live in constraints |
| `duckdb_constraints()` | `database_name, database_oid, schema_name, schema_oid, table_name, table_oid, constraint_index, constraint_type, constraint_text, expression, constraint_column_indexes, constraint_column_names, constraint_name, referenced_table, referenced_column_names` | PK/FK/CHECK/NOT NULL/UNIQUE |
| `duckdb_functions()` | 21 columns incl. `function_name, function_type, parameters, parameter_types, return_type, macro_definition, has_side_effects, extension_name, examples` | signature lookup (`match_bm25`, macros) |
| `duckdb_extensions()` | `extension_name, loaded, installed, install_path, description, aliases, extension_version, install_mode, installed_from, signature_key_fingerprint` | pre/post-upgrade checks |
| `duckdb_settings()` | `name, value, description, input_type, scope, aliases, typed_value` | checkpoint/temp/storage settings |
| `duckdb_secrets()` | `name, type, provider, persistent, storage, scope, secret_string` | names/types only; never paste `secret_string` |

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| 110 | The manual's table-function page is incomplete for 2.0: it omits `duckdb_databases.encrypted/cipher`, `duckdb_schemas.parent_schema*`, `duckdb_columns.tags`, `duckdb_views.is_bound`, `duckdb_extensions.signature_key_fingerprint`, `duckdb_settings.aliases/typed_value`; `duckdb_databases().database_oid` is documented VARCHAR but is BIGINT, while `duckdb_functions().database_oid` is documented BIGINT but is VARCHAR. | `DESCRIBE SELECT * FROM ...` vs `sql/meta/duckdb_table_functions.md`. | Probed |
| 111 | `duckdb_tables().schema_name` is the leaf name for a nested schema (`reports`), not `finance.reports`; join `duckdb_schemas()` on `schema_oid = oid` to recover `parent_schema`. | `CREATE SCHEMA finance.reports`; join returned `finance, reports, r`. | Probed |
| 112 | `SHOW ALL TABLES` is the compact cross-database overview: `database, schema, name, column_names, column_types, temporary`. | `SHOW ALL TABLES` on a two-DB session. | Probed |

## Existing skill audit

Audited snapshots: docs `8af9a0b8`, migrate `abef6621`, checklist `574dabd6`, session `bda31305`.

| Skill | Claim or omission | Verdict | Fix |
|---|---|---|---|
| docs | "`2.0`, `blog` ... no `lts`, `current`, or `stable` slice" | correct | Keep. |
| docs | "2695 chunks at `2.0` and 999 at `blog`" (moved to `research/09`) | correct | Keep; add DuckLake 198. |
| docs | "Refresh when ... older than two days" | thin | Add version-row/ETag check and "use stale cache with a warning if refresh fails". |
| docs | "Open the cache as the main database, not as an attached catalog" | correct, thin | Add `-readonly`; mention `USE alias` also works. |
| docs | "`match_bm25` has side effects ... Wrap it in a subquery" | correct, thin | Say only `WHERE`/`QUALIFY` alias references need it; `ORDER BY score` works without. |
| docs | "The signature is `match_bm25(input_id, query, fields, k, b, conjunctive)`" | thin | Actual macro has `field_weights`, `field_b`, `scoring_model`, `tie_breaker`; the manual page is stale. |
| docs | "`fields := 'text'` only when you need to exclude the title and section" | correct | Keep; index fields are `page_title`, `section`, `text`. |
| docs | "set `conjunctive := 0`" when no results | thin | Default is already 0; only useful after `conjunctive := 1`. |
| docs | "If the index is unreachable ... link docs" | thin | Add direct remote `ATTACH ...; USE remote;` fallback (verified, ~5 s). |
| docs | "DuckLake `stable` is the 1.1 manual" | correct | Keep. |
| docs | Query block does not show `-readonly` | thin | Add it; a read-write open blocks concurrent readers. |
| migrate | "New files ... storage version 69" | correct | Add that `tags` reports `v2.0.0+`, not `69`. |
| migrate | "2.0 can read and write older files, and those writes keep the old storage version" | correct by default, thin | Add: `ATTACH ... (STORAGE_VERSION 'latest')` + write upgrades to 69. |
| migrate | "`latest` means version 69" | correct, thin | Same upgrade trap. |
| migrate | "`SET storage_compatibility_version`; `ATTACH ... (STORAGE_VERSION ...)`" | thin | `SET` after startup does not affect the main DB; use `-storage-version` at startup or `SET` before attach. |
| migrate | "1.5.6 reports ... 64 through 68" | correct, thin | Add that 1.5.6's default new file is 64; 68 is opt-in. |
| migrate | "`error_on_division_by_zero=false` ... the setting is deprecated" | correct | The skill matches the binary; the manual is the stale source. Keep the warning. |
| migrate | `EXPORT DATABASE 'tmp'` / `IMPORT DATABASE 'tmp'` | correct, thin | Default is CSV; import fails on same-named objects; export dir should be empty. |
| migrate | `COPY FROM DATABASE old TO new` | thin | Target may be non-empty but must have no same-named objects; its `STORAGE_VERSION` controls output. |
| migrate | Order: inventory, pin, shadow, backup, upgrade, SQL checks, cutover | thin | Backup before shadow; run static SQL checks before upgrade; add explicit rollback gate. |
| migrate | "A storage upgrade in place is not reversible" | too strong | A 2.0 `COPY FROM DATABASE` into a `STORAGE_VERSION 'v1.5.6'` target is a tested down-copy; a backup is still required. |
| migrate | Verification creates a table in `memory` and expects `v2.0.0+` | wrong | `tags['storage_version']` is NULL for `memory`; use a temp file path or attach a file. |
| migrate | No `amalgamation`, `glibc 2.28`, `windows_arm64` | thin | Add to the deployment matrix/reference. |
| checklist | Pre-flight `SELECT table_schema ... FROM duckdb_tables()` | wrong | Column is `schema_name`; query fails with `Referenced column "table_schema" not found`. |
| checklist | `sqlite_master(`, `read_any(` listed as 2.0 hits | thin | Both are absent in 1.5.6 too; not 2.0-specific. Drop or label pre-2.0. |
| checklist | "Rollback ... not reversible" | too strong | Add the 2.0 down-copy recipe and test it. |
| session | "One process writes ... Other processes open it `READ_ONLY`" | wrong | A writer excludes readers; many readers only when no writer. Fix the sentence and name Quack/DuckLake. |
| session | "For a backup, `EXPORT DATABASE` writes a directory of SQL and Parquet" | wrong | Default is CSV; require `(FORMAT parquet)`. |
| session | "`tags['storage_version']` is the version to trust" | thin | It is a compatibility floor; 1.5.6's 64 file reports `v1.0.0+`; `options` shows the requested string. |
| session | "The alias is the file stem" | thin | Stem is up to the first dot; quote `-`, spaces, leading digits. |
| session | "Append only when that path is not already attached" | thin | `ATTACH IF NOT EXISTS` is alias-keyed; missing paths are created; duplicate path under a new alias errors. |
| session | "`.duckdb-skills/state.sql` ... the path used by the older duckdb-skills plugin" | wrong | Upstream currently uses it; `.duckdb/state.sql` is this pack's convention. |
| session | "Add `USE` ... only when ... the state file has no `USE` yet" | correct, thin | Without any `USE`, the default is `memory`, so `SHOW TABLES` shows memory; validate with a qualified query or add one `USE`. |
| session | "`STORAGE_VERSION 'v1.5.0'` — Create a file that older DuckDB versions can read" | thin | Creation only; a lower version on an existing file errors. |
| session | "Closing a Python connection does not release every file lock" | wrong/overgeneralized | On the only connection it does release; locks persist while another connection/instance holds the file. |
| session | "`CHECKPOINT` fails ... `FORCE CHECKPOINT` waits from 1.4 onward" | correct | Keep. |
| session | "`COPY FROM DATABASE analytics TO archive`" | thin | `archive` must be attached and free of same-named objects; add the `ATTACH`. |
| session | No temp-directory, `.gitignore`, or secret-key-id detail | thin | Add one compact "files and locks" paragraph. |

## Gaps worth adding

| Rank | Gap | Why an agent needs it | Home |
|---|---|---|---|
| 1 | Native concurrency is one writer **or** many readers, never both; a writer blocks read-only processes. | The current session skill says readers can open while a writer runs, which produces a hard lock error in production. | `duckdb-session/SKILL.md` |
| 2 | `ATTACH existing (STORAGE_VERSION 'latest')` + write silently upgrades to 69; lower versions error. | A "harmless" attach option can make a file unreadable by 1.5.6; the first 16-byte header still looks old. | `duckdb-migrate/SKILL.md` + one line in session |
| 3 | Tags are compatibility floors (`v2.0.0+`, `v1.5.0+`, `v1.0.0+`); 1.5.6's default file is 64, not 68. | Agents will otherwise report the wrong version and misjudge rollback. | `duckdb-migrate/SKILL.md` storage table |
| 4 | `ATTACH IF NOT EXISTS` is alias-keyed, creates a missing file, and silently no-ops on an alias conflict. | A typo in a state file creates a new 69 database; a moved project keeps the old path. | `duckdb-session/SKILL.md` |
| 5 | Migration order needs backup before shadow, plus an explicit rollback gate and refusal list. | The current order can run a shadow before a verified backup; agents need a stop condition. | `duckdb-migrate/SKILL.md` + `references/checklist.md` |
| 6 | `EXPORT DATABASE` defaults to CSV; `IMPORT` fails on same-named objects; `COPY FROM DATABASE` aborts on conflicts and keeps unrelated objects. | "Backup as Parquet" and "copy into a used DB" both mislead. | session one line; checklist detail |
| 7 | Docs cache must be opened `-readonly`; a read-write open locks out other agents. | Concurrent docs questions are common in a multi-agent session. | `duckdb-docs/SKILL.md` |
| 8 | `match_bm25` has 10 params; `stemmer`/`stopwords`/`ignore` belong to `create_fts_index`; `bm25_k1`/`bm25_b` do not exist. | Wrong parameter names produce a binder error; the manual page is stale. | `duckdb-docs/SKILL.md` |
| 9 | `SET storage_compatibility_version` after startup does not change the main DB. | Agents will set it in `-c` and believe the file is pinned. | `duckdb-migrate/SKILL.md` |
| 10 | Deployment matrix: C++17, amalgamation deprecated, glibc 2.28, `osx_amd64` partial, extension rebuilds, Python 3.11. | Custom builds and older Macs fail for reasons unrelated to SQL. | `duckdb-migrate/references/checklist.md` |
| 11 | Python 3.11+ and the 15 API breaks are only a cross-link. | A Python deployment can pass SQL checks and still fail at runtime. | `duckdb-python` (owner); one line in migrate |
| 12 | `-init` semantics: SQL + dot commands, errors exit 1, CLI-only, default stays `memory` without `USE`. | Agents misdiagnose an empty `SHOW TABLES` or a silent state file. | `duckdb-session/SKILL.md` |
| 13 | State path reconciliation: upstream `.duckdb-skills` vs this pack's `.duckdb`; project-id is the git root. | Two state files split the session; `$HOME` projects collide with `~/.duckdb`. | `duckdb-session/SKILL.md` |
| 14 | Stale-index detection beyond mtime. | A two-day-old cache can miss a release-day page; a failed refresh should not discard a working cache. | `duckdb-docs/SKILL.md` |
| 15 | `duckdb_secrets()` hides `secret=` but shows `key_id=`. | Pasting the result leaks the access-key ID. | `duckdb-session/SKILL.md` |
| 16 | Catalog docs are stale; use `DESCRIBE` and the 2.0 column lists. | Agents copy a column that does not exist (e.g., `table_schema`). | session one line; no reference |

`skills/duckdb-migrate/references/checklist.md` is **justified and already present** (185 lines). It carries the long inventory, grep, conversion, and cutover tables that would bloat `SKILL.md`; the repo plan explicitly allows a migration reference. Keep it, but fix the `table_schema` bug, the in-memory verify, the backup ordering, and the "not reversible" wording. Do **not** add a docs reference (the 10-param table fits in `SKILL.md`) or a session catalog reference (`DESCRIBE` is authoritative and the full column list is low-value).

## Traps and contradictions

| Trap | What happens | Correct move | Evidence |
|---|---|---|---|
| Tag looks like an exact version | A 64 file made by 1.5.6 reports `v1.0.0+`; a 68 file pinned by 2.0 reports `v1.5.0+`; only 69 reports `v2.0.0+`. | Treat the tag as a floor; use the storage table/header for the number, and `options` for the requested string. | Probes #31-32, #42 |
| `hexdump` after an in-place upgrade | First 16 bytes still say 64/68; the database header says 69; 1.5.6 refuses. | Trust `tags`/`duckdb_databases()`, not the first header. | #37 |
| `ATTACH ... STORAGE_VERSION` on an existing file | Lower version errors; `latest` upgrades on the next write. | Use it only at creation; for existing files use `COPY FROM DATABASE` into a new target. | #37-38 |
| `SET storage_compatibility_version` in `-c` | The main DB is already open; the SET affects only later attaches. | Use `-storage-version` at startup or `SET` before `ATTACH`. | #40 |
| Manual recommends `error_on_division_by_zero` | Binary warns it is deprecated; `PRAGMA enable_profiling` also warns to use `SET enable_profiling`. | Prefer `TRY(expr)`; use `SET enable_profiling` for profiling. | #54, probe log |
| FTS manual signature is six params | Actual macro has 10; `stemmer`/`stopwords`/`ignore` are create-index options. | Use `duckdb_functions()` or the binder candidate list; see #10-13. | #10-13 |
| Attached FTS macro | `alias.fts_main_docs_chunks.match_bm25(...)` fails because the macro body is unqualified. | Open the cache as main, or `USE alias`. | #18 |
| Same-SELECT alias filter | `WHERE score IS NOT NULL` and `QUALIFY` fail; `ORDER BY score` works. | Wrap in a subquery/CTE when filtering on the alias. | #15-16 |
| `ATTACH IF NOT EXISTS` with a typo | Creates a new 69 file, so the session "works" against an empty database. | `test -f` first; check the alias; ask before creating. | #98 |
| Duplicate path under a new alias | `Unique file handle conflict`; the attach fails. | Reuse the existing alias; one file per session. | #98 |
| `EXPORT DATABASE` "backup" | Default is CSV, not Parquet; a non-empty dir keeps stale files. | `(FORMAT parquet)`; empty dir; test the import. | #44-45 |
| `COPY FROM DATABASE` into a used DB | Same-named objects abort with `Table ... already exists`; unrelated objects stay. | Use a conflict-free target; `(SCHEMA)` for schema-only. | #43 |
| Session skill's concurrency sentence | Readers cannot open while a writer holds the file. | One writer or many readers; Quack/DuckLake for multi-writer. | #102 |
| `.duckdb/state.sql` in `$HOME` | Mixes the state file into `~/.duckdb`, alongside `extensions` and `stored_secrets`. | Prefer `.duckdb-skills/state.sql`, or keep `.duckdb/` only for non-home projects. | #108 |
| `duckdb_secrets()` looks safe | `secret=` is redacted, `key_id=` is not. | Report names/types only; never paste the row. | #107 |

## What not to add

- Full column tables for every `duckdb_*()` function: the manual page is already stale, and `DESCRIBE` is one command. Keep only the summary query and the 8 useful columns.
- The full 15-item Python migration list in `duckdb-migrate`: `duckdb-python` owns it; migrate needs only Python 3.11 + storage config + a cross-link.
- Storage history before version 64 and `VACUUM` as a space-reclaim step: compatibility starts at 64, and `VACUUM` does not reclaim deleted rows.
- A separate DuckLake docs skill/cache and HTML scraping: the schema is identical; the index already has text and URLs.
- Recommending `ATTACH OR REPLACE` or `ATTACH ... STORAGE_VERSION` on an existing file as routine operations: both are destructive.
- Storing literal secrets in `state.sql`: even persistent secrets are unencrypted; use `getenv()`/`credential_chain`.

## Probe log

```text
$ duckdb --version
v2.0.0 (Cyanoptera) d54cbbe3df
$ ./v155/duckdb --version; ./v156/duckdb --version
v1.5.5 (Variegata) d8cdaa33fd
v1.5.6 (Variegata) 069cc9f9b5

# Docs index
$ curl -sSL -o duckdb-docs.duckdb https://duckdb.org/data/docs-search.duckdb   # 15,216,640 bytes
$ duckdb -readonly duckdb-docs.duckdb -c "SELECT version,count(*) FROM docs_chunks GROUP BY 1"
2.0=2695, blog=999; total 3694, distinct chunk_id 3694 (DuckLake: stable=198)
$ duckdb -readonly duckdb-docs.duckdb -c "SELECT * FROM fts_main_docs_chunks.fields"
0 page_title, 1 section, 2 text
$ duckdb duckdb-docs.duckdb -c "SELECT page_title, fts_main_docs_chunks.match_bm25(chunk_id,'variant shredding') AS score FROM docs_chunks WHERE version='2.0' AND score IS NOT NULL"
Binder Error: Alias ""score"" referenced - but the expression has side effects. This is not yet supported.
$ duckdb -readonly duckdb-docs.duckdb -c "<subquery with WHERE score IS NOT NULL LIMIT 3>"
Variant Type / Parquet Support 7.50; Variant Type / Storage 7.08; Geometry / Storage 4.92
$ duckdb -c "ATTACH ... AS remote; SELECT readonly FROM duckdb_databases()"
remote true; CREATE TABLE fails: attached in read-only mode
$ duckdb -c "INSTALL httpfs; ... COPY FROM DATABASE remote TO tmp"
7.6 s; cache 13 MB; 2.0=2695, blog=999

# match_bm25 parameters
$ duckdb -readonly duckdb-docs.duckdb -c "SELECT fts_main_docs_chunks.match_bm25(chunk_id,'variant', stemmer:='english') ..."
Binder Error: Macro match_bm25() does not support the supplied arguments.
Candidate: match_bm25(docname, query_string, fields := NULL, k := 1.2, b := 0.75, conjunctive := false, field_weights := NULL, field_b := NULL, scoring_model := 'bm25f', tie_breaker := 0.0)
(stopwords/ignore/bm25_k1/bm25_b fail the same way; k/b/field_weights/scoring_model work)

# Storage
$ duckdb default.db -c "CREATE TABLE t(x INT)"
$ duckdb -json default.db -c "SELECT database_name,tags,tags['storage_version'] FROM duckdb_databases()"
default {storage_version=v2.0.0+} v2.0.0+
$ hexdump -n 20 -C default.db
... DUCK e7 03 00 00 ...   # 999
$ duckdb old.db -storage-version v1.5.6 -c "CREATE TABLE t(x INT)"
tags v1.5.0+; header 0x44 (68)
$ ./v156/duckdb default.db -c "SELECT 1"; ./v155/duckdb default.db -c "SELECT 1"
v1.5.6: version number 69, can only read 64..68; v1.5.5: version number 999, can only read 64..68
$ ./v156/duckdb v156.db -c "SELECT 1"   # default 1.5.6 file
header 0x40 (64), tag v1.0.0+
$ duckdb v156.db -c "INSERT INTO t VALUES (2)"
tag v1.0.0+; header 0x40; v1.5.6 reads it
$ duckdb -c "ATTACH 'default.db' (STORAGE_VERSION 'v1.5.6')"
cannot initialize database with storage version 68 - which is lower than what the database itself uses (69)
$ cp old.db upgrade-test.db; duckdb -c "ATTACH 'upgrade-test.db' AS u (STORAGE_VERSION 'latest'); CREATE TABLE u.newtab AS SELECT 1"
tag v2.0.0+; ./v156/duckdb upgrade-test.db -> file was written with a storage version greater...
$ duckdb -c "ATTACH 'old.db' AS src (READ_ONLY); ATTACH 'conv.db' AS dst (STORAGE_VERSION 'v1.5.6'); COPY FROM DATABASE src TO dst"
down.db tags v1.5.0+; v1.5.6 reads
$ duckdb old.db -c "INSERT ...; CHECKPOINT"
old.db stays 68; 1.5.6 still reads

# Export/import/copy
$ duckdb old.db -c "EXPORT DATABASE 'expdefault'"
expdefault/{schema.sql,load.sql,t.csv}   # default CSV
$ duckdb -c "IMPORT DATABASE 'expdefault'" on non-empty DB
Catalog Error: Table with name "t" already exists!
$ duckdb -c "ATTACH old AS src (READ_ONLY); ATTACH default.db AS dst; COPY FROM DATABASE src TO dst"
Catalog Error: Table with name "t" already exists!  (target with only `other` kept it and added `t`)
$ duckdb -c "COPY FROM DATABASE ... TO dst (SCHEMA)"
dst.t count = 0

# Session
$ duckdb -init state2.sql -c "SELECT current_database(); SHOW ALL TABLES"
one; one.main.a, two.main.b
$ duckdb -init dots.sql -c "SELECT * FROM range(5)"
.maxrows applied; banner on stderr
$ duckdb -init baddot.sql -c "SELECT 1"
Unknown Command Error ... Encountered errors while executing init file "baddot.sql". Exiting.
$ duckdb -c "ATTACH IF NOT EXISTS 'missing.db' AS one"
creates missing.db (12288 bytes, header 999)
$ duckdb -c "ATTACH 'alias-one.db'; CREATE TABLE alias-one.t(x INT)"; duckdb -c "ATTACH 'alias-one.db' AS a1; ATTACH 'alias-one.db' AS a2"
Parser Error at "-"; second command: Unique file handle conflict
$ duckdb -c "ATTACH 'alias-one.db' AS a1; ATTACH IF NOT EXISTS 'alias-two.db' AS a1"
a1 keeps alias-one.db; alias-two is not attached
$ duckdb s1.db -c "DETACH s1"
Cannot detach database "s1" because it is the default database...
$ duckdb -c "SET checkpoint_on_detach='DISABLED'; ATTACH 'det.db' AS d; INSERT ...; DETACH d"
det.db.wal remains; reattach sees the row
$ duckdb -c "SET checkpoint_on_detach='ENABLED'; ... DETACH"
det.db.wal removed
$ duckdb wal.db -c "INSERT ..."; ls
wal.db, wal.db.wal (276 bytes); CHECKPOINT -> wal.db only

# Concurrency (separate processes)
$ python hold_rw.py & python try_ro.py
RO ERROR: IO Error: Could not set lock ... Conflicting lock is held ... See https://duckdb.org/docs/current/connect/concurrency
$ python ro1.py & python ro2.py
ro2 OK
$ python close_hold.py & python try_ro.py
closed; RO OK

# Catalog
$ duckdb -c "DESCRIBE SELECT * FROM duckdb_databases()"
database_name, database_oid, path, comment, tags, internal, type, readonly, encrypted, cipher, options
(duckdb_schemas/tables/columns/views/indexes/constraints similarly; see section 8)
$ duckdb -c "SELECT table_schema FROM duckdb_tables()"
Binder Error: Referenced column "table_schema" not found; candidate "schema_name"
$ duckdb -c "SELECT s.parent_schema,t.schema_name,t.table_name FROM duckdb_tables() t JOIN duckdb_schemas() s ON t.schema_oid=s.oid"
finance, reports, r

# Migration settings / CLI
$ duckdb -c "SELECT list_transform([1,2,3], x -> x+1)"
Binder Error: Deprecated lambda arrow (->) detected...
$ duckdb -c "SET lambda_syntax='enable_single_arrow'; SELECT list_transform([1,2,3], x -> x+1)"
[2,3,4]
$ duckdb -c "SELECT 1//0;"
Invalid Input Error: Division by zero in expression (1 // 0). Use TRY(...) ...
$ duckdb -c "SET error_on_division_by_zero=false; SELECT 1//0,1%0,1/0"
WARNING: setting is deprecated; NULL, NULL, inf
$ duckdb -c "SET custom_profiling_settings='{}'"
unrecognized configuration parameter "custom_profiling_settings"
$ duckdb -c "SET enable_http_logging=true"
unrecognized configuration parameter "enable_http_logging"
$ duckdb -c "SET profiling_mode='detailed'; SELECT 1"
WARNING: profiling_mode is deprecated...
$ duckdb -c "SET preserve_identifier_case='bogus'"
Unrecognized parameter ... expected preserve_case, lowercase, uppercase
$ duckdb -c "SET table_function_identifier_conversion='ENABLE_IMPLICIT_STRING'"
WARNING: setting is deprecated
$ duckdb -c "SELECT 'xERRORy' ~ 'ERROR'"
2.0 true; 1.5.6 false
$ duckdb -c "SET enable_legacy_parser=true; SELECT 1"
ok (autoloads)
$ duckdb -c "SELECT * FROM read_any('x.csv')"; ./v156/duckdb -c "SELECT sqlite_master('x')"
read_any absent in both; sqlite_master absent in both (not 2.0-specific)

# Agent mode / limits
$ AI_AGENT=1 duckdb -c "SELECT 42"
stderr banner; stdout Markdown table
$ AI_AGENT=1 duckdb -json -c "SELECT 42"
[{"answer":42}] (-csv prints plain CSV; -no-agent prints a box table)
$ duckdb -c "SET max_execution_time=1; SELECT count(*) FROM range(100000000) a, range(100) b"
{"exception_type":"INTERRUPT","exception_message":"Query exceeded maximum execution time"}
(SET enable_profiling='json' produced a JSON profile; PRAGMA enable_profiling warns to use SET)
```

## Open questions

- Does `ATTACH ... (STORAGE_VERSION 'latest')` upgrade on the first write or only on checkpoint? The probe wrote a table and closed; the file was 69 and 1.5.6 refused. A crash-before-checkpoint probe would show whether the WAL alone carries the new version.
